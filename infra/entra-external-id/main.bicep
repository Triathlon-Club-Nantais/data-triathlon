// Tenant externe Entra External ID du club (#1323).
// Déployé dans le groupe de ressources existant : voir AGENTS.md du dossier.
// Gratuit jusqu'à 50 000 utilisateurs actifs par mois ; aucun module payant
// (domaine personnalisé, SMS) n'est déclaré ici.

@description('Nom du tenant, qui devient <nom>.onmicrosoft.com et le sous-domaine <nom>.ciamlogin.com.')
@minLength(1)
@maxLength(26)
param tenantName string

@description('Nom affiché du tenant.')
param displayName string

resource tenant 'Microsoft.AzureActiveDirectory/ciamDirectories@2023-05-17-preview' = {
  name: '${tenantName}.onmicrosoft.com'
  location: 'Europe'
  sku: {
    name: 'Standard'
    tier: 'A0'
  }
  properties: {
    createTenantProperties: {
      countryCode: 'FR'
      displayName: displayName
    }
  }
}

output tenantId string = tenant.properties.tenantId
output subdomain string = tenantName
