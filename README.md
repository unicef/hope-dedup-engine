ABOUT HOPE Payment Gateway
==========================


## Contributing

### System Requirements

- python 3.11
- [direnv](https://direnv.net/) - not mandatory but strongly recommended
- [pdm](https://pdm.fming.dev/2.9/)




**WARNING**  
> Hope Payment Gateway implements **security first** policy. It means that configuration default values are "almost" production compliant.
> 
> Es. `DEBUG=False` or `SECURE_SSL_REDIRECT=True`. 
> 
> Be sure to run `./manage.py env --check` and  `./manage.py env -g all` to check and display your configuration
 


### 1. Clone repo and install requirements
    git clone https://github.com/unicef/hope-dedup-engine 
    pdm venv create 3.11
    pdm install
    pdm venv activate in-project
    pre-commit install

### 2. configure your environment

Uses `./manage.py env` to check required (and optional) variables to put 

    ./manage.py env --check


### 3. Run upgrade to run migrations and initial setup

    ./manage.py upgrade

# Troubleshoot
> Exception are logged in Sentry: https://sentry.io/unicef-jk/
