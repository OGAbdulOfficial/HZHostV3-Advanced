Process:

remove 

#"--net={net_access}"

in deployment_helper if you want to put custom networking device get from ifconfig.

Firejail:

wget https://github.com/netblue30/firejail/releases/download/0.9.74/firejail_0.9.74_1_amd64.deb
sudo apt install ./firejail_0.9.74_1_amd64.deb

FileBowser:

curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash

filebrowser config init -d projects/filebrowser.db

filebrowser -d projects/filebrowser.db users add admin sunning112233# --perm.admin

# Now run the server
filebrowser -r projects -p 8080 -d projects/filebrowser.db --noauth

Fake SHIM:
# Run this once on your server
sudo mkdir -p /opt/bytesupreme_safeguards/dotenv
sudo chown -R your_user:your_user /opt/bytesupreme_safeguards # Give your app's user ownership
