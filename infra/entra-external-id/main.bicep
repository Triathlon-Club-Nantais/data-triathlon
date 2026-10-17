// Tenant externe Entra External ID du club (#1323).
// Déployé dans le groupe de ressources existant : voir AGENTS.md du dossier.
// Gratuit jusqu'à 50 000 utilisateurs actifs par mois ; aucun module payant
// (domaine personnalisé, SMS) n'est déclaré ici.

@description('Nom du tenant, lettres et chiffres seuls : il devient <nom>.onmicrosoft.com et le sous-domaine <nom>.ciamlogin.com.')
@minLength(1)
@maxLength(26)
param tenantName string

@description('Nom affiché du tenant.')
param displayName string

// Valeurs vérifiées contre la référence ARM (relevé du 2026-10-11) :
// https://learn.microsoft.com/en-us/azure/templates/microsoft.azureactivedirectory/ciamdirectories
// `name` porte le suffixe « .onmicrosoft.com » (exigé par la validation
// préalable d'Azure le 2026-10-12, contrairement au motif de la référence),
// `location` parmi
// 'United States', 'Europe', 'Asia Pacific', 'Australia', `sku.tier` A0, seule
// valeur admise. `sku.name` Base : la référence liste Standard, mais la
// validation préalable d'Azure le refuse et exige Base (mesuré le 2026-10-12).
resource tenant 'Microsoft.AzureActiveDirectory/ciamDirectories@2023-05-17-preview' = {
  name: '${tenantName}.onmicrosoft.com'
  location: 'Europe'
  sku: {
    name: 'Base'
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
