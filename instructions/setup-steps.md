Install screen (if not already installed):

'''{r, engine='bash', count_lines}
sudo apt-get install screen
'''

Start a new screen session:
'''console
screen -S mysession
'''
Run your application inside the screen session:

'''console
python my_app.py
'''
Detach from the screen session without stopping the process: Press Ctrl + A, then D.

List all screen sessions (optional):
'''console
screen -ls
'''
Reattach to the screen session later:

'''console
screen -r mysession
'''
