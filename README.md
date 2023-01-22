# Swim With The Tide (swtt) 
## Summary
Swim With The Tide is a simple python script that decrements the ppm on your channels when they're inactive for a given period of time.  

Operations Summary:  
1. It uses SQLite3 to keep track of forwarding and channel infomation.  
2. The SQLite3 database file is ```swtt.db``` in the /home/swtt/swtt directory.  
3. Deleting swtt.db will reset all channel PPM's to the specified starting value (--starting_ppm).  
4. The max HTLC size will be 99% of local balance (This could be optional parameter in future release)  
5. The base fee is set to 0, zero base fee is important for an optimized LN: https://youtu.be/WoVPkmT3gjY?t=2220  
6. The CLTV (Time Lock Delta) is 144 by default (Could be optional parameter in future)  
7. The current state of all channels is saved in the CSV swtt_current_channel_info.csv.  
8. Script actions and errors are logged to ```swtt.log``` in the same directory as the script  

Manual run example: ```swtt.py -s 100 -t 1d -d 10 -m 5```  

## Parameters
### Required
```-s``` or ```--starting_ppm``` Starting PPM for all new channels expressed as an integer.  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;(e.g. ```-s 100``` will start the channels at 100 ppm)  

```-t```  or ```--stale_time``` Stale time before decrementing the ppm expressed as a string in days or hours.  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;(e.g. ```-t 2d``` or ```-t 48h``` will decrement the ppm when the channel hasn't forwarded an HTLC for 2 days)  

```-d``` or ```--decrement_ppm``` The amount to decrement the ppm expressed as an integer.  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;(e.g. ```-d 10``` will decrement all channels by 10 ppm for every stale time cycle that passes without a forward)  

```-m``` or ```--min_ppm``` The minimum ppm a channel should be (ppm floor) expressed as an integer.  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;(e.g. ```-m 5``` will ensure your channel charges at minimum 5 ppm, it won't go lower than this)  

## Setup
### Install dependencies
Review, edit and run the ```setup.sh``` file based on your distribution, or simply run the commands one at a time.
The main things that need to be setup are:
1. Add the user "swtt" and give it access to the "lnd" and "bos" groups
2. Give "swtt" group access to your admin user
3. Install Python and Virtual-Env
4. Create the "swtt" virtual environment inside of the home dir (/home/swtt/)
5. Activate Python and install required packages via pip
6. Upload swtt.py to the virtual environment directory (/home/swtt/swtt/)

### Install Cron Job
I suggest running the script every 30 minutes to 1 hour.

As the swtt user: ```crontab -e```  
```*/30 * * * * cd /home/swtt/swtt && /home/swtt/swtt/bin/python3.9 /home/swtt/swtt/swtt.py -s 100 -t 1d -d 10 -m 5```  

## Logging
Logs are stored in the same folder as the script: /home/swtt/swtt/swtt.log