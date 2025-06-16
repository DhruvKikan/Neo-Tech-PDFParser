SSH into AWS instance from CMD:

`
ssh -i <path-to-key> <username/ubuntu>@<ip> (ip will be there on AWS dashboard)
`

SCP to transfer files:

`
scp -i <path-to-key> <file-zip> <username/ubuntu>@<ip>:/home/ubuntu
`

Unzip the file:

`
<look it up>
`

Base installations:
`
sudo apt install python3\
sudo apt install nginx\
pip install -r requirements\
python3 run app.py
`

Configure reverse proxy:

Navigate to /etc/nginx/sites-enabled
Create new file named same as the deployment public IP address 

`
sudo nano "<public IP>"
`

Configuration/Contents

`
server {
    listen 80;
    listen [::]:80;
    server_name <Instance IP>;
    location / {
        proxy_pass http://127.0.0.1:5000;
        include proxy_params;
    }
}
`

Install screen:

`
sudo apt-get install screen
`

Start a new screen session:

`
screen -S <session_name/mysession>
`

Run your application inside the screen session:

`
python my_app.py
`

Restart nginx server:

`
sudo systemctl restart nginx/
sudo systemctl status nginx
`

Detach from the screen session without stopping the process: Press Ctrl + A, then D.

List all screen sessions (optional):

`
screen -ls
`

Reattach to the screen session later:

`
screen -r <session_name/mysession>
`
