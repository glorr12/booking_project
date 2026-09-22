#!/bin/bash
set -e

sudo dnf update -y
sudo dnf install -y docker git

sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

sudo dnf install -y docker-compose-plugin

sudo systemctl restart docker

sg docker -c '
    cd /opt

    sudo git clone https://github.com/glorr12/booking_project booking_project
    sudo git clone https://github.com/glorr12/rental-frontend rental-frontend
    cd booking_project

    if [ ! -f .env ]; then
        echo "!!! .env отсутствует - создай его вручную перед следующим шагом (см. инструкцию) !!!"
        exit 1
    fi

    sudo docker compose up -d --build
'