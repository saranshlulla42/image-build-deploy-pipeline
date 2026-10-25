targetScope = 'resourceGroup'

param location string = resourceGroup().location
param vmName string = 'image-pipeline-vm'
param vmSize string = 'Standard_B2als_v2'
param adminUsername string = 'pipelineadmin'
@description('Public SSH key only. The network does not expose SSH.')
param sshPublicKey string
@description('Exact GitHub OIDC subject for the demo environment, including immutable repository IDs when applicable.')
param githubSubject string
param shutdownTime string = '2300'
param shutdownTimeZone string = 'India Standard Time'

var tags = { project: 'image-build-deploy-pipeline', purpose: 'student-demo' }
var init = '''
#cloud-config
write_files:
  - path: /opt/image-pipeline/bootstrap.sh
    permissions: '0700'
    encoding: b64
    content: ${base64(loadTextContent('bootstrap.sh'))}
  - path: /opt/image-pipeline/bootstrap.yaml
    permissions: '0600'
    encoding: b64
    content: ${base64(loadTextContent('../../k8s/bootstrap.yaml'))}
runcmd:
  - [bash, /opt/image-pipeline/bootstrap.sh]
'''

resource nsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: '${vmName}-nsg'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'public-demo-http'
        properties: {
          priority: 100
          access: 'Allow'
          direction: 'Inbound'
          protocol: 'Tcp'
          sourceAddressPrefix: 'Internet'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '80'
        }
      }
    ]
  }
}
resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: '${vmName}-vnet'
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: ['10.60.0.0/16'] }
    subnets: [{ name: 'demo', properties: { addressPrefix: '10.60.1.0/24', networkSecurityGroup: { id: nsg.id } } }]
  }
}
resource ip 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: '${vmName}-ip'
  location: location
  tags: tags
  sku: { name: 'Standard' }
  properties: { publicIPAllocationMethod: 'Static', publicIPAddressVersion: 'IPv4' }
}
resource nic 'Microsoft.Network/networkInterfaces@2024-05-01' = {
  name: '${vmName}-nic'
  location: location
  tags: tags
  properties: {
    ipConfigurations: [{ name: 'primary', properties: {
      privateIPAllocationMethod: 'Dynamic'
      subnet: { id: '${vnet.id}/subnets/demo' }
      publicIPAddress: { id: ip.id }
    } }]
  }
}
resource vm 'Microsoft.Compute/virtualMachines@2024-03-01' = {
  name: vmName
  location: location
  tags: tags
  properties: {
    hardwareProfile: { vmSize: vmSize }
    storageProfile: {
      imageReference: { publisher: 'Canonical', offer: 'ubuntu-24_04-lts', sku: 'server', version: 'latest' }
      osDisk: { createOption: 'FromImage', diskSizeGB: 32, deleteOption: 'Delete', managedDisk: { storageAccountType: 'StandardSSD_LRS' } }
    }
    osProfile: {
      computerName: vmName
      adminUsername: adminUsername
      customData: base64(init)
      linuxConfiguration: {
        disablePasswordAuthentication: true
        provisionVMAgent: true
        ssh: { publicKeys: [{ path: '/home/${adminUsername}/.ssh/authorized_keys', keyData: sshPublicKey }] }
      }
    }
    networkProfile: { networkInterfaces: [{ id: nic.id, properties: { primary: true, deleteOption: 'Delete' } }] }
  }
}
resource shutdown 'Microsoft.DevTestLab/schedules@2018-09-15' = {
  name: 'shutdown-computevm-${vmName}'
  location: location
  tags: tags
  properties: {
    status: 'Enabled'
    taskType: 'ComputeVmShutdownTask'
    dailyRecurrence: { time: shutdownTime }
    timeZoneId: shutdownTimeZone
    targetResourceId: vm.id
    notificationSettings: { status: 'Disabled' }
  }
}
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${vmName}-github'
  location: location
  tags: tags
}
resource federation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: identity
  name: 'github-demo-environment'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: githubSubject
    audiences: ['api://AzureADTokenExchange']
  }
}
resource role 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: guid(resourceGroup().id, 'image-pipeline-run-command')
  properties: {
    roleName: 'Image pipeline VM deployer ${uniqueString(resourceGroup().id)}'
    description: 'Read and execute action Run Command on the dedicated demo VM only. Root command access is intentionally limited to this VM.'
    type: 'CustomRole'
    assignableScopes: [resourceGroup().id]
    permissions: [{ actions: ['Microsoft.Compute/virtualMachines/read', 'Microsoft.Compute/virtualMachines/runCommand/action'], notActions: [], dataActions: [], notDataActions: [] }]
  }
}
resource assignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vm.id, identity.id, role.id)
  scope: vm
  properties: { principalId: identity.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: role.id }
}
output publicUrl string = 'http://${ip.properties.ipAddress}'
output vmResourceId string = vm.id
output githubClientId string = identity.properties.clientId
output tenantId string = tenant().tenantId
output subscriptionId string = subscription().subscriptionId
