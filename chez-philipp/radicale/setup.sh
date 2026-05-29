#!/bin/sh

# Create htpasswd file if it doesn't exist
if [ ! -f /data/users ]; then
  echo "Creating user: ${RADICALE_USER:-philipp}"
  python3 -c "
import bcrypt, os
user = os.environ.get('RADICALE_USER', 'philipp')
password = os.environ.get('RADICALE_PASSWORD', 'geheim123')
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
with open('/data/users', 'w') as f:
    f.write(f'{user}:{hashed}\n')
print(f'User {user} created.')
"
fi

exec python3 -m radicale --config /etc/radicale/config
