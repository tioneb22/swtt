# Swim With The Tide (swtt) 
## Summary
Swim With The Tide is a simple python script that decrements the ppm on your channels when they're inactive for a given period of time.  
It uses SQLite3 to keep track of forwarding and channel infomation. The database file is ```swtt.db``` in the /home/swtt/swtt directory.  
Deleting the swtt.db file will reset all channel PPM's to the specified starting value (--starting_ppm).  

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
4. Create the "swtt" virtual environment inside of /home/swtt
5. Activate Python and install required packages via pip

### Install Cron Job
I suggest running the script every 30 minutes to 1 hour.

As the swtt user: ```crontab -e```  
```*/30 * * * * cd /home/swtt/swtt && /home/swtt/swtt/bin/python3.9 /home/swtt/swtt/swtt.py -s 100 -t 1d -d 10 -m 5```  

## Logging
Logs are stored in the same folder as the script: /home/swtt/swtt/swtt.log