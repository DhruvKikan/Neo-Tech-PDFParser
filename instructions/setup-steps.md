Install screen (if not already installed):

'''
sudo apt-get install screen
'''

Start a new screen session:

'''
screen -S mysession
'''

Run your application inside the screen session:

'''
python my_app.py
'''

Detach from the screen session without stopping the process: Press Ctrl + A, then D.

List all screen sessions (optional):

'''
screen -ls
'''

Reattach to the screen session later:

'''
screen -r mysession
'''
