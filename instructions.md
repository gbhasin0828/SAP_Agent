Here is the complete ordered list of every command to deploy this from scratch.

PRE-REQUISITES

Docker Desktop installed and running
Azure CLI installed
Node.js installed
Git repo with code pushed


## STEP 1 — Login to Azure
az login
az account set --subscription YOUR_SUBSCRIPTION_ID

## STEP 2 — Create Resource Group
az group create --name sap-agent-rg --location eastus

## STEP 3 — Register Providers
az provider register --namespace Microsoft.ContainerRegistry
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.Storage
az provider register --namespace Microsoft.Web
Wait 60 seconds then verify all show "Registered":
az provider show --namespace Microsoft.ContainerRegistry --query registrationState
az provider show --namespace Microsoft.App --query registrationState
az provider show --namespace Microsoft.OperationalInsights --query registrationState
az provider show --namespace Microsoft.Storage --query registrationState
az provider show --namespace Microsoft.Web --query registrationState

## STEP 4 — Create Container Registry
az acr create --resource-group sap-agent-rg --name sapagentregistry --sku Basic --admin-enabled true

## STEP 5 — Build and Push Docker Image
cd C:\Users\Work\Desktop\Demos\SAP_Agent\backend
docker build -t sap-agent .
az acr login --name sapagentregistry
docker tag sap-agent sapagentregistry.azurecr.io/sap-agent:latest
docker push sapagentregistry.azurecr.io/sap-agent:latest

## STEP 6 — Create Storage Account and File Share
az storage account create --name sapagentstore26 --resource-group sap-agent-rg --location eastus --sku Standard_LRS
az storage share create --name sap-agent-db --account-name sapagentstore26
az storage file upload --account-name sapagentstore26 --share-name sap-agent-db --source "C:\Users\Work\Desktop\Demos\SAP_Agent\backend\sap_equipment.db" --path sap_equipment.db
Get storage key (save this for later):
az storage account keys list --account-name sapagentstore26 --resource-group sap-agent-rg --query "[0].value" -o tsv

## STEP 7 — Create Container Apps Environment
az containerapp env create --name sap-agent-env --resource-group sap-agent-rg --location eastus
Register File Share with Container Apps Environment:
az containerapp env storage set --name sap-agent-env --resource-group sap-agent-rg --storage-name sapdbstorage --azure-file-account-name sapagentstore26 --azure-file-account-key YOUR_STORAGE_KEY --azure-file-share-name sap-agent-db --access-mode ReadWrite

## STEP 8 — Deploy Container App
az containerapp create --name sap-agent --resource-group sap-agent-rg --environment sap-agent-env --image sapagentregistry.azurecr.io/sap-agent:latest --registry-server sapagentregistry.azurecr.io --registry-username sapagentregistry --registry-password $(az acr credential show --name sapagentregistry --query "passwords[0].value" -o tsv) --target-port 8000 --ingress external --min-replicas 1 --max-replicas 1 --secrets anthropic-key=YOUR_ANTHROPIC_API_KEY

## STEP 9 — Set Env Vars and Mount Database via YAML
Create backend/containerapp.yaml:
yamlproperties:
  template:
    volumes:
      - name: sapdb
        storageType: AzureFile
        storageName: sapdbstorage
    containers:
      - name: sap-agent
        image: sapagentregistry.azurecr.io/sap-agent:latest
        env:
          - name: ANTHROPIC_API_KEY
            secretRef: anthropic-key
          - name: SAP_URL
            value: https://YOUR_STATIC_WEB_APP_URL/fake_sap.html
          - name: SAP_USERNAME
            value: demo
          - name: SAP_PASSWORD
            value: demo123
        volumeMounts:
          - volumeName: sapdb
            mountPath: /app/sap_equipment.db
            subPath: sap_equipment.db
```

Then run:
```
az containerapp update --name sap-agent --resource-group sap-agent-rg --yaml containerapp.yaml


**STEP 10 — Scale Up Compute**

az containerapp update --name sap-agent --resource-group sap-agent-rg --cpu 2 --memory 4Gi

## STEP 11 — Deploy Frontend
Add GitHub secret AZURE_STATIC_WEB_APPS_API_TOKEN to your repo, then create .github/workflows/deploy-frontend.yml:
yamlname: Deploy Frontend

on:
  push:
    branches:
      - feature/docker-deployment

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: Azure/static-web-apps-deploy@v1
        with:
          azure_static_web_apps_api_token: ${{ secrets.AZURE_STATIC_WEB_APPS_API_TOKEN }}
          repo_token: ${{ secrets.GITHUB_TOKEN }}
          action: upload
          app_location: frontend
          skip_app_build: true
```

Create Static Web App:
```
az staticwebapp create --name sap-agent-frontend --resource-group sap-agent-rg --location eastus2 --sku Free
```

Get deployment token:
```
az staticwebapp secrets list --name sap-agent-frontend --resource-group sap-agent-rg --query "properties.apiKey" -o tsv
```

Push to GitHub — GitHub Actions deploys automatically.

---

**VERIFY EVERYTHING IS WORKING**
```
# Check container is running
az containerapp show --name sap-agent --resource-group sap-agent-rg --query "properties.runningStatus"

# Check health endpoint
curl https://YOUR_CONTAINER_APP_URL/health

# Check logs if something is wrong
az containerapp logs show --name sap-agent --resource-group sap-agent-rg --tail 50
```

---

**TO ROTATE ANTHROPIC KEY**
```
az containerapp secret set --name sap-agent --resource-group sap-agent-rg --secrets anthropic-key=YOUR_NEW_KEY
az containerapp revision restart --name sap-agent --resource-group sap-agent-rg
```

---

**TO TEARDOWN EVERYTHING**
```
az group delete --name sap-agent-rg --yes