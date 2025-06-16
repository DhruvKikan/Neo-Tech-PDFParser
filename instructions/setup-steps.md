SSH into AWS instance from CMD:

`
ssh -i <path-to-key> <username/ubuntu>@<ip>` (ip will be there on AWS dashboard)


SCP to transfer files:

`
scp -i <path-to-key> <file-zip> <username/ubuntu>@<ip>:/home/ubuntu
`

Pre-requisites:
`sudo add-apt-repository universe`
`sudo apt-get update`  
`sudo apt-get upgrade`

Unzip the file:

`sudo apt-get install unzip`  
`unzip <file_name.zip> (optional -d distination_folder)`


Base installations:

`sudo apt install python3`  
`sudo apt install python3-pip`  
`sudo apt install nginx`  
`sudo apt install python3-venv`  
`sudo apt-get install -y tesseract-ocr libgl1-mesa-glx libglib2.0-0`  
`python3 -m venv my-project-env`  

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

`source my-project-env/bin/activate`  
`pip install -r requirements.txt`  
`python3 app.py`


Restart nginx server:

`
sudo systemctl restart nginx
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
