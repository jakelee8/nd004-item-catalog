# Inventory

This repository is my submission for the Item Catalog Webapp for the
[Full Stack Web Developer Nanodegree][nd004] program at [Udacity][udacity].
The web application is called "Inventory" and organizes items into
categories and allows registered users to manage the items.

Inventory is implemented in Python using [Flask][flask],
[SQLAlchemy][sqlalchemy] with [PostgreSQL][postgresql], and
[Zurb Foundation][foundation].

Note: [SQLite][sqlite] is used during development. PostgreSQL is used during
deployment.

## Prerequisites

Inventory can be installed as a Python module that will automatically
resolve dependencies. However, I recommend that you run Fresh Tomatoes using
[Anaconda][anaconda] to keep your system's Python installation clean.
Anaconda is a popular Python installer and package manager widely used in
the Data Science community. Follow the [link to install Anaconda][anaconda].

Once you have Anaconda installed, clone the code from [GitHub][github].

```sh
git clone https://github.com/jakelee8/inventory && cd inventory
```

If you are using Anaconda, run the `./bin/conda_env` script from the project
directory to set up the Python environment for Fresh Tomatoes.

```sh
./bin/conda_env
```

Regardless of whether you are using Anaconda, running the `./bin/dev` script
from the project directory will start the Flask application in development
mode. Note that by default, Inventory will create a SQLite database at
`/tmp/inventory.sqlite`. If this is not acceptable, remember to change
the script accordingly before starting the app.

```sh
# Create local app configuration
cat <<EOL | tee app.cfg
# DATABASE = 'postgresql://catalog:<password>@localhost/catalog'
# SECRET_KEY = '<secret-key>'
GOOGLE_OAUTH_CLIENT_ID = '<app-id>.apps.googleusercontent.com'
GOOGLE_OAUTH_CLIENT_SECRET = '<client-secret>'
EOL

# Configure app to use local configuration
export INVENTORY_SETTINGS=$PWD/app.cfg

# Start the app in dev mode
./bin/dev
```

If the script runs without errors, Inventory will be accessible at

> http://127.0.0.1:5000

## JSON API

The app implements two read-only JSON endpoints: the item list and the item
details.

The item list is available at:

`http://127.0.0.1:5000/items.json`

The item details, given an item ID is available at:

`http://127.0.0.1:5000/items/<item_id>.json`


## Deploy

This guide is written for deploying to a cloud virtual machine of
[Amazon Lightsail][lightsail] running Ubuntu 16.04. Documentation on how to
create and access a new cloud virtual machine are available on the [Amazon
Sail website][lightsail].

### Configure the server

After launching a suitable machine on Amazon Lightsail or other provider,
SSH into the machine to configure it.

```sh
ssh ubuntu@<ip-address>
```

1. Update the software on the virtual machine.

```sh
sudo apt-get update
sudo apt-get upgrade -y
```

2. Install the Apache web server and the PostgreSQL database along with the
Python 3 module for WSGI to allow Apache to serve the Inventory app.

```sh
sudo apt-get install -y apache2 libapache2-mod-wsgi-py3 postgresql
```

3. Change the default SSH configuration.

```
# /etc/ssh/sshd_config

# Change SSH port from the default of 22 to 2200
Port 2200

# Disable root login
PermitRootLogin no

# Disable password login
PasswordAuthentication no

# Require RSA authentication
RSAAuthentication yes

# Remove or comment the following line to disable public key authentication
# This will disable any Amazon-issued SSH keys using this method.
#PubkeyAuthentication yes
```

Tell the SSH server to reload the configuration.

```sh
# After editing /etc/ssh/sshd_config
sudo systemctl reload sshd
```

Disconnect from the server and reconnect via port 2200.

```sh
ssh -p 2200 ubuntu@<ip-address>
```

4. Enable the firewall using the `ufw` utility. If it is not already
installed, run `sudo apt install -y ufw` to install it.

Before enabling the firewall on the cloud virtual machine instance, ensure
that the Amazon Lightsail network configurations allow port 2200. Otherwise,
you will not be able to access the instance using SSH over port 2200.

```sh
# Check existing rules
ufw status verbose

# Default to denying incoming connections
ufw default deny incoming

# Default to allowing all outgoing connections
ufw default allow outgoing

# Enable incoming HTTP requests on port 80
ufw allow http

# Enable incoming NTP (time server) requests on port 123
ufw allow ntp

# Enable incoming SSH requests over port 2200
ufw allow 2200

# Enable the firewall
ufw enable

# Check firewall status
ufw status verbose
```

Update the Amazon Lightsail network configuration to reflect the firewall
configuration. Documentation is available on the
[Amazon Lightsail][lightsail] website.

For a tutorial on how to use `ufw`, see this great
[article from DigitalOcean][ufw-tutorial].

5. Configure PostgreSQL.

Open a PostgreSQL shell with administrative privileges.

```sh
sudo su postgres -C 'psql -U postgres'
```

Create the user `catalog` and grant access to the database `catalog`.

```sql
-- Create user catalog
CREATE USER catalog;

-- Set password for user catalog
\password catalog
-- enter password interactively

-- Create database catalog
CREATE DATABASE catalog;

-- Grant access to database catalog to user catalog
GRANT ALL ON DATABASE catalog TO catalog;
```

For a tutorial on how to manage PostgreSQL permissions, see this great
[article from DigitalOcean][postgres-tutorial].

6. Configure Apache web server.

```sh
# Create the WSGI user and group
adduser --system inventory-app
addgroup --system inventory-app
adduser inventory-app inventory-app

# Enable WSGI module
sudo ln -s /etc/apache2/mods-available/wsgi.load /etc/apache2/mods-enabled/wsgi.load

# Create root directory
sudo mkdir -p /var/www/inventory

# Create configuration file
cat <<EOL | sudo tee /var/www/inventory.cfg
DATABASE = 'postgresql://catalog:<password>@localhost/catalog'
SECRET_KEY = '<secret-key>'
GOOGLE_OAUTH_CLIENT_ID = '<app-id>.apps.googleusercontent.com'
GOOGLE_OAUTH_CLIENT_SECRET = '<app-secret>'
EOL

# Create WSGI entrypoint
cat <<EOL | sudo tee /var/www/inventory/inventory.wsgi
import os
os.environ['INVENTORY_SETTINGS'] = '/var/www/inventory.cfg'
from inventory import app as application
EOL

# Configure Apache to serve the Inventory app
cat <<EOL | sudo tee /etc/apache2/sites-enabled/inventory-app.conf
<VirtualHost *:80>
    ServerName inventory.jakelee.net

    WSGIDaemonProcess inventory user=inventory-app group=inventory-app threads=4
    WSGIProcessGroup inventory
    WSGIApplicationGroup %{GLOBAL}
    WSGIScriptAlias / /var/www/inventory/inventory.wsgi

    <Directory /var/www/inventory>
        Order allow,deny
        Allow from all
    </Directory>
</VirtualHost>
EOL

# Tell Apache to reload the configuration
sudo systemctl reload apache2
```

7. Install and configure Inventory app.

```sh
# Clone the source code from GitHub
git clone https://github.com/jakelee8/nd004-item-catalog.git

# Install the application
sudo pip3 install -U ./nd004-item-catalog

# Initialize the database with demo data
FLASK_APP=inventory FLASK_DEBUG=1 INVENTORY_SETTINGS=/var/www/inventory.cfg flask initdb
```

### Configure Google API for authentication

1. Open the [Google API Console][google-console].
2. Click on the "Credentials" link in the left sidebar.
3. Click on the "Credentials" tab in the main content area.
4. Click on the "Create credentials" button and select "OAuth client ID".
5. Select "Web application" for application type.
6. Provide an appropriate name for the Client ID.
7. Set the "Authorized JavaScript origins" to the web server hostname. e.g.
  - http://inventory.jakelee.net
8. Set the "Authorized JavaScript origins" to the OAuth2 callback URL. e.g.
  - http://inventory.jakelee.net/signin/callback
9. Click "Create".

The Inventory application should now be viewable on the web.

### 9. (Optional) Create the `grader` user for the Udacity project requirements.

The `grader` user is used by Udacity graders and needs a SSH key and sudo
permission.

```sh
# Create the grader user
sudo adduser --system grader

# Generate a SSH key for user grader
sudo su grader -- ssh-keygen

# Authorize SSH login using the SSH key
sudo su grader -- cp /home/grader/.ssh/id_rsa.pub /home/grader/.ssh/authorized_users

# Grant sudo permission to user grader
echo 'grader ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/91-grader
```


[udacity]: https://www.udacity.com
[nd004]: https://classroom.udacity.com/nanodegrees/nd004
[flask]: http://flask.pocoo.org
[postgresql]: https://www.postgresql.org
[sqlite]: https://www.sqlite.org
[sqlalchemy]: http://docs.sqlalchemy.org
[foundation]: http://foundation.zurb.com
[anaconda]: https://www.continuum.io/anaconda-overview
[github]: https://github.com/jakelee8/fresh_tomatoes
[lightsail]: https://lightsail.aws.amazon.com/
[google-console]: https://console.developers.google.com/apis/credentials

[ufw-tutorial]: https://www.digitalocean.com/community/tutorials/how-to-set-up-a-firewall-with-ufw-on-ubuntu-14-04
[postgres-tutorial]: https://www.digitalocean.com/community/tutorials/how-to-use-roles-and-manage-grant-permissions-in-postgresql-on-a-vps--2
