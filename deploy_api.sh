#!/usr/bin/env bash

./deploy.sh function && ./deploy.sh function02 && ./deploy.sh api && ./deploy.sh permission

if [ $ALIS_APP_ID = 'alis' ] || [ $ALIS_APP_ID = 'staging' ]; then
  ./deploy.sh apialarms
fi
