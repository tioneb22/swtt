# -*- coding: utf-8 -*-
"""
Swim With The Tide - SWTT

Version 0.1 beta
    -Tracks channel activity and decrements fee's until the ppm sweet-spot is reached

Usage:
    e.g. $ python3.9 swtt.py -s 100 -t 1d -d 10 -m 5
    
    -s 100  -->  Start channels at 100ppm
    -t 1d   -->  Decrement after 1 day of inactivity (no forwards)
    -d 10   -->  Decrement by 10 ppm each time
    -m 5    -->  Don't decrement below 5 ppm (ppm floor)
    
"""
###########
# LOGGING #
###########
import logging
logging.basicConfig(
    filename='swtt.log',   
    filemode = "a",
    level=logging.INFO, 
    format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s')


###########
# IMPORTS #
###########
import subprocess
import pandas as pd
import json
import argparse
import numpy as np
import sqlite3
import os
from datetime import datetime, timedelta
import re


########
# Args #
########
# arg menu setup
parser = argparse.ArgumentParser()
required = parser.add_argument_group('required arguments')

# required args
required.add_argument('--starting_ppm', '-s', help="Starting PPM for routes, it will decrement from here if not routing.", type=int, required=True)
required.add_argument('--decrement_ppm', '-d', help="PPM decrement after each failed rebalancing attempt.", type=int, required=True)
required.add_argument('--min_ppm', '-m', help="Minimum PPM to route (PPM floor)", type=int, required=True)
required.add_argument('--stale_time', '-t', help="Amount of time to wait before decrementing PPM in hours or days (e.g, 6h, 12h, 1d, 7d)", type=str, required=True)

# optional args

# parse the args
args = parser.parse_args()


###########
# GLOBALS #
###########
# counters
chan_changes = 0

# argument variables
arg_starting_ppm = args.starting_ppm
arg_decrement_ppm = args.decrement_ppm
arg_min_ppm = args.min_ppm
arg_stale_time = args.stale_time

# sqlite variables
con = sqlite3.connect('swtt.db')
cur = con.cursor()

# SQL formattable's
sql_tbl_forwarding_insert = "INSERT INTO tbl_forwarding VALUES ('{cid}', '{lct}', '{lft}', '{ldt}', '{nc}')"
sql_tbl_forwarding_update_all = "UPDATE tbl_forwarding SET last_check_time = '{lct}', last_forward_time = '{lft}', last_decrement_time = '{ldt}', new_chan = '{nc}' WHERE chan_id = '{cid}'"
sql_tbl_forwarding_update_lct = "UPDATE tbl_forwarding SET last_check_time = '{lct}', new_chan = '{nc}' WHERE chan_id = '{cid}'"
sql_tbl_forwarding_update_lct_lft = "UPDATE tbl_forwarding SET last_check_time = '{lct}', last_forward_time = '{lft}', new_chan = '{nc}' WHERE chan_id = '{cid}'"
sql_tbl_forwarding_update_lct_ldt = "UPDATE tbl_forwarding SET last_check_time = '{lct}', last_decrement_time = '{ldt}', new_chan = '{nc}' WHERE chan_id = '{cid}'"

# LNCLI formattable's
lncli_get_new_fwds = "/usr/local/bin/lncli fwdinghistory --start_time -{s}h --max_events 10000"
lncli_update_channel = "/usr/local/bin/lncli updatechanpolicy --base_fee_msat 0 --fee_rate_ppm {ppm} --time_lock_delta 144 --max_htlc_msat {mhtlc} --min_htlc_msat 1000 --chan_point {cp}"

# display options
pd.options.display.float_format = "{:.2f}".format
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


#############
# Functions #
#############
# function to check and setup variables
def setup_vars():
    global arg_starting_ppm,arg_decrement_ppm,arg_min_ppm,arg_stale_time
    global dt_lct_thresh,dt_now,stale_time,starting_ppm
    
    # check and format stale time variable
    if arg_stale_time == None or containsNumber(arg_stale_time)==False:
        logging.info("Argument 'stale_time' isn't formatted properly.")
        raise ValueError("Argument 'stale_time' isn't formatted properly.")
    else:
        
        if 'h' in arg_stale_time:
            h = extract_int(arg_stale_time)
        elif 'd' in arg_stale_time:
            h = extract_int(arg_stale_time) * 24
        else:
            logging.info("Argument 'stale_time' isn't formatted properly.")
            raise ValueError("Argument 'stale_time' isn't formatted properly.")

        dt_lct_thresh = datetime.now() - timedelta(hours=h)
        
    # Setup other needed variables
    dt_now = datetime.now()             # runtime DT var
    stale_time = h                      # stale lookup back * 2 (use in new forwards lookup)
    starting_ppm = arg_starting_ppm     # setup starting ppm variable
    
    return
    
# function to setup sqlite tables if db is empty
def setup_db():
    global con,cur
    db = os.path.expanduser("~")+"/swtt/swtt.db"
    
    # if size bigger than 0, it's already initialized
    if os.path.getsize(db) > 0:

        # get active channel list in table "tbl_channels"
        build_tbl_channels()
    else:
        # create main table that will track forwards
        cur.execute("CREATE TABLE tbl_forwarding(chan_id PRIMARY KEY, last_check_time, last_forward_time, last_decrement_time, new_chan)")
        
        # import all recent forwards
        dfFwds = pd.DataFrame.from_dict(pd.json_normalize(json.loads(get_proc_output("/usr/local/bin/lncli fwdinghistory --start_time -12M --max_events 10000"))['forwarding_events']), orient='columns')
        dfFwds = dfFwds.iloc[::-1] # reverse index so new forwards list first
        
        # get active channel list in table "tbl_channels"
        build_tbl_channels()
        
        # loop through active channels and find most recent forward
        dfChan = pd.read_sql_query("SELECT * FROM tbl_channels", con)   # get DF of channels
        for chan_id in dfChan['chan_id'].to_list():
            for row in dfFwds.itertuples():
                if chan_id == row.chan_id_out:
                    cur.execute(sql_tbl_forwarding_insert.format(cid=chan_id,lct=dt_now,lft=int(row.timestamp),ldt=dt_now,nc='1'))
                    break
            else:
                cur.execute(sql_tbl_forwarding_insert.format(cid=chan_id,lct=dt_now,lft=0,ldt=dt_now,nc='1'))
                continue
        con.commit()
        log = 'DB created, size is now ' + str(os.path.getsize(db))
        logging.info(log)
    
# simple function to extract numbers from string
def extract_int(string):
    return int(re.findall(r'\d*', string)[0])

# function to find if string contains number
def containsNumber(value):
    for character in value:
        if character.isdigit():
            return True
    return False
    
# function to run shell commands
def get_proc_output(cmd):
    process = subprocess.Popen(
        cmd,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE)
    # process.wait() # cause lenghty commands to hang
    data, err = process.communicate()
    if process.returncode == 0:
        return data.decode('utf-8')
    else:
        log_err = "Error: " + str(err)
        logging.info(log_err)
        raise ValueError(log_err)
    return ""

# function to return node alias from pubkey using lncli getnodeinfo --pub_key 
def return_alias(row):
    _command = "/usr/local/bin/lncli getnodeinfo --pub_key " + row.remote_pubkey
    return json.loads(get_proc_output(_command))['node']['alias']

# function to determine if peer is sink or source
def return_peer_type(row):
    if row.send_ratio > 1.33:
        return 'sink'
    elif row.send_ratio < 0.66:
        return 'source'
    
# function to get current max HTLC size for given chan_id
def return_max_htlc(row):
    # load json data from lncli command
    js = json.loads(get_proc_output("/usr/local/bin/lncli getchaninfo --chan_id {cid}".format(cid=row.chan_id)))
    # loop every policy to find latest data, return max htlc in sats
    for item in js:
        if 'policy' in item:
            # when the policy matches the last update
            if js[item]['last_update'] == js['last_update']:
                return int(js[item]['max_htlc_msat'][:-3])
    
# function to return list of all chan_id's 
def build_tbl_channels():
    global con,cur
    
    # get json output of lncli command then send to pandas dataframe
    dfChan = pd.DataFrame.from_dict(pd.json_normalize(json.loads(get_proc_output("/usr/local/bin/lncli listchannels"))['channels']), orient='columns')
    
    # make df of channel fees then join it to dfChan
    dfFee = pd.DataFrame.from_dict(pd.json_normalize(json.loads(get_proc_output("/usr/local/bin/lncli feereport"))['channel_fees']), orient='columns')
    dfChan = pd.merge(dfChan,dfFee,on=['chan_id','channel_point'])

    # Build DF (calculate ratios etc...)
    dfChan['alias'] = dfChan.apply(lambda row: return_alias(row), axis=1)           # get node alias as new column
    dfChan['htlc_size'] = dfChan.apply(lambda row: return_max_htlc(row),axis=1)     # get max htlc size for given chan id
    dfChan.rename(columns = {'fee_per_mil':'ppm',
                            'total_satoshis_sent':'sent',
                            'total_satoshis_received':'received'},inplace=True)     # shorten certain column names
    dfChan['sent'] = pd.to_numeric(dfChan['sent'])                                  # convert to numeric
    dfChan['ppm'] = pd.to_numeric(dfChan['ppm'])                                    # convert to numeric
    dfChan['received'] = pd.to_numeric(dfChan['received'])                          # convert to numeric
    dfChan['send_ratio'] = dfChan['sent'] / dfChan['received']                      # add send ratio column
    dfChan["local_balance"] = pd.to_numeric(dfChan["local_balance"])                # convert to numeric
    dfChan["remote_balance"] = pd.to_numeric(dfChan["remote_balance"])              # convert to numeric
    dfChan['balance_ratio'] = dfChan["local_balance"] / dfChan["remote_balance"]    # find local percentage ratio
    dfChan["capacity"] = pd.to_numeric(dfChan["capacity"])                          # convert to numeric
    dfChan["sats_missing_for_balance"] = (dfChan["capacity"] / 2) - dfChan["local_balance"]                             # find satoshi delta in order to have balanced channel
    dfChan['active_ratio'] = (dfChan['sent'] + dfChan['received']) / (dfChan['sent'].sum() + dfChan['received'].sum())  # find how active channel is compared to others
    dfChan['sats_missing_for_balance'] = dfChan['sats_missing_for_balance'].map('{:,}'.format)                          # format column with commas
    dfChan['local_balance'] = dfChan['local_balance'].map('{:,}'.format)            # format column with commas
    dfChan['remote_balance'] = dfChan['remote_balance'].map('{:,}'.format)          # format column with commas
    dfChan['type'] = dfChan.apply(return_peer_type, axis = 1)                       # apply node type function
    
    # keep only required columns
    dfChan = dfChan[['chan_id','channel_point','alias','remote_pubkey','local_balance','remote_balance','ppm','htlc_size','send_ratio','type','balance_ratio',"sats_missing_for_balance",'active_ratio']]
    
    # Replace table in DB
    cur.execute("DROP TABLE IF EXISTS tbl_channels")
    dfChan.to_sql(name='tbl_channels',con=con)
    con.commit()
    return

# function to tweak channels and update tbl_forwarding table
def update_channel(utype,alias,cp,cid,new_ppm,new_mhtlc,lft,ldt):
    global con,cur,chan_changes
    
    # update SQL DB depending on type
    if utype == 'new':
        failed_list = json.loads(get_proc_output(lncli_update_channel.format(ppm=new_ppm,mhtlc=new_mhtlc,cp=cp)))['failed_updates'] # if update successful, this returns empty list
        cur.execute(sql_tbl_forwarding_update_lct.format(cid=cid, lct=dt_now, nc='0'))
        log = "Setup new channel for " + alias + " (" + cid + ") / " + str(new_ppm) + " ppm / Max HTLC Size: " + str(new_mhtlc/1000) + " sats"
        logging.info(log)
        chan_changes +=1
    elif utype == 'fwd':
        failed_list = [] # initialize empty list so funcion doesn't error out
        cur.execute(sql_tbl_forwarding_update_lct_lft.format(cid=cid, lct=dt_now, lft=lft, nc='0'))
    elif utype == 'dec':
        failed_list = json.loads(get_proc_output(lncli_update_channel.format(ppm=new_ppm,mhtlc=new_mhtlc,cp=cp)))['failed_updates'] # if update successful, this returns empty list
        cur.execute(sql_tbl_forwarding_update_lct_ldt.format(cid=cid, lct=dt_now, ldt=dt_now, nc='0'))
        log = "Decremented Channel PPM for " + alias + " (" + cid + ") / " + str(new_ppm) + " ppm / Max HTLC Size: " + str(new_mhtlc/1000) + " sats"
        logging.info(log)
        chan_changes +=1
    con.commit()
    
    # if error is in list from LNCLI update, exit script by raising error
    if not failed_list:
        return True # will go to next channel when returning True
    else:
        error = "Error while updating channel: " + str(failed_list)
        logging.info(error)
        raise ValueError(error)
    return

# Main function that controls changes to channels
def update_forwarding():
    global con,cur

    # Prereqs before looping through channels
    dfChan = pd.read_sql_query("SELECT * FROM tbl_channels", con)           # get DF of channels
    dfFwd = pd.read_sql_query("SELECT * FROM tbl_forwarding", con)          # get DF of forwarding state
    
    # Retrieve new forwards based on stale time then reverse index so new forwards are first
    dfNewFwds = pd.DataFrame.from_dict(pd.json_normalize(json.loads(get_proc_output(lncli_get_new_fwds.format(s=stale_time)))['forwarding_events']), orient='columns')
    dfNewFwds = dfNewFwds.iloc[::-1] # reverse order
    
    # Loop channels, compare last_forward_time, last_decrement_time
    for chan_row in dfChan.itertuples():
        
        # Configure variables for later use
        chan_id = chan_row.chan_id
        chan_point = chan_row.channel_point
        chan_ppm = chan_row.ppm
        alias = chan_row.alias
        new_mhtlc = int(float(chan_row.local_balance.replace(',','')) * 0.99) * 1000    # multiple by 1000 to get msat
        
        # configure tbl_forwarding variables
        chan_fwd_lct = dfFwd.loc[dfFwd['chan_id']==chan_id,'last_check_time'].item()
        chan_fwd_lft = dfFwd.loc[dfFwd['chan_id']==chan_id,'last_forward_time'].item()
        chan_fwd_ldt = dfFwd.loc[dfFwd['chan_id']==chan_id,'last_decrement_time'].item()
        
        # Check if channel is new from initial setup
        if dfFwd.loc[dfFwd['chan_id']==chan_id,'new_chan'].item() == '1':
            
            # update channel and continue outer loop if there are no errors
            if update_channel('new',alias,chan_point,chan_id,starting_ppm,new_mhtlc,chan_fwd_lft,chan_fwd_ldt):
                continue
        
        # When channel is new but DB is already setup
        if chan_id not in dfFwd['chan_id'].to_list():
            
            # Add new channel to tbl_forwarding
            cur.execute(sql_tbl_forwarding_insert.format(cid=chan_id,lct=dt_now,lft=0,ldt=dt_now,nc='1'))
            
            # update channel and continue outer loop if there are no errors
            if update_channel('new',alias,chan_point,chan_id,starting_ppm,new_mhtlc,chan_fwd_lft,chan_fwd_ldt):
                continue

        # if new forwards DF isn't blank and there's a new forward for given channel 
        if  len(dfNewFwds)!=0:
            if chan_id in dfNewFwds['chan_id_out'].to_list():
        
                # for each forward in new forwards DF / find latest forward for channel
                for fwd_row in dfNewFwds.itertuples():
                    
                    # get timestamp of current forward
                    cur_fwd_ts = int(fwd_row.timestamp)
        
                    # if chan_id matches and it's a new forward
                    if chan_id == fwd_row.chan_id_out and chan_fwd_lft < cur_fwd_ts:
                        
                        # update channel and continue outer loop if there are no errors
                        if update_channel('fwd',alias,chan_point,chan_id,0,new_mhtlc,cur_fwd_ts,chan_fwd_ldt):
                            break
                continue
                
        # else there's no new forwards, potentially decrement PPM
        else:
            
            # get datetime from string
            chan_fwd_lct_dt = datetime.strptime(chan_fwd_lct, '%Y-%m-%d %H:%M:%S.%f')
            
            # if the last check time is stale compared to threshold, decrement ppm
            if chan_fwd_lct_dt < dt_lct_thresh:
                
                # ppm logic
                dec_ppm = chan_ppm - arg_decrement_ppm
                
                # don't decrement if already at floor
                if dec_ppm <= arg_min_ppm:
                    dec_ppm = arg_min_ppm
                    
                # update channel and continue outer loop if there are no errors
                if update_channel('dec',alias,chan_point,chan_id,dec_ppm,new_mhtlc,chan_fwd_lft,chan_fwd_ldt):
                    continue
    return
    

####################
# Run main program #
####################
if __name__ == "__main__":
    setup_vars()            # Check and setup vars
    setup_db()              # Setup and initialize DB for first time use and update channel DB with latest channel information
    update_forwarding()     # Update latest forward information
    build_tbl_channels()    # Update channel info in case of changes
    
    # print the current state of channels
    dfCurInfo = pd.read_sql_query("SELECT c.alias,c.chan_id,c.local_balance,c.ppm,c.htlc_size,f.last_check_time,f.last_forward_time,f.last_decrement_time FROM tbl_forwarding f INNER JOIN tbl_channels c ON c.chan_id = f.chan_id", con)
    dfCurInfo.to_csv('swtt_current_channel_info.csv',index=False)   
    
    # log successful run of script
    log  = "Script ran successfully, " + str(chan_changes) + " channels were updated" 
    logging.info(log)
    
    # commit then close SQL connection
    con.commit()
    con.close()
    