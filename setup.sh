# Setup user account with proper access
sudo adduser --gecos "" --disabled-password swtt
sudo adduser admin swtt # give your admin user access to swtt
sudo adduser swtt bos # give swtt access to bos
sudo adduser swtt lnd # give swtt access to lnd


# Install python
# Python already installed
# https://howtoforge.com/how-to-install-python-on-debian-11/

# Create Python virtual environment for swtt & setup lncli access
sudo apt install python3-dev virtualenv -y 	# Install virtualenv
sudo su - swtt 								# change user
virtualenv --python=python3 ~/swtt 			# make new virtual environment
ln -s /mnt/data/lnd /home/swtt/.lnd 		# sym link for .lnd director, for lncli use


# Install reqired env packages with pip
source ~/swtt/bin/activate 					# activate new environment
pip3 install pandas
pip3 install argparse
pip3 install sqlite3