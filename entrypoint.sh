#!/bin/sh -l
set -ex
# pour detection healthcheck du rproxy et relance suite a rechargement app
echo "" >  /app/nginx/default.conf 

export USE_UV=0
export USE_DOCKER=0 # Commands run from inside docker shouldn't be prefixed

just deploy

#creation conf nginx rproxy 
ownip=`hostname -i`
# reinit conf
echo "" >  /app/nginx/default.conf 
tee -a /app/nginx/default.conf << EOF
    server { 
	server_name $ownip;
	listen $CONTAINER_PORT;
	location / {
	    proxy_pass http://$ownip:$HOST_PORT;
	    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
	    proxy_set_header X-Forwarded-Proto \$scheme;
	    proxy_set_header Host \$host;
	    proxy_set_header X-Real-IP \$remote_addr;
	}
EOF
if [ ! "$DEBUG" = "True" ]; then
# rajout static and medias via nginx en mode prod voir doc django
tee -a /app/nginx/default.conf << EOF
	error_page   500 502 503 504 404  /404/;
	location /staticfiles/ { 
	    alias /usr/share/nginx/html/static/;
	}
	location /medias/ { 
	    alias /usr/share/nginx/html/medias/;
	}
EOF
fi
tee -a /app/nginx/default.conf << EOF
    }
EOF

if [ "$DEBUG" = "True" ]; then
    python manage.py runserver 0.0.0.0:$HOST_PORT
else
    gunicorn config.wsgi:application --bind 0.0.0.0:$HOST_PORT
fi

exec "$@"
