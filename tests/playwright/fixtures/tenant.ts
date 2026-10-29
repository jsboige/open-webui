/**
 * Multi-tenant configuration loader.
 * Reads credentials from environment variables (loaded from .env at repo root).
 */

export interface TenantConfig {
  name: string;
  url: string;
  email: string;
  password: string;
}

const TENANTS: Record<string, { urlEnv: string; emailEnv: string; passwordEnv: string; defaultUrl: string }> = {
  myia: {
    urlEnv: 'MYIA_URL',
    emailEnv: 'MYIA_EMAIL',
    passwordEnv: 'MYIA_PASSWORD',
    defaultUrl: 'https://open-webui.myia.io',
  },
  epf: {
    urlEnv: 'EPF_URL',
    emailEnv: 'EPF_EMAIL',
    passwordEnv: 'EPF_PASSWORD',
    defaultUrl: 'https://epf.open-webui.myia.io',
  },
  'epf-genai': {
    urlEnv: 'EPF_GENAI_URL',
    emailEnv: 'EPF_GENAI_EMAIL',
    passwordEnv: 'EPF_GENAI_PASSWORD',
    defaultUrl: 'https://genai.epf.open-webui.myia.io',
  },
  ece: {
    urlEnv: 'ECE_URL',
    emailEnv: 'ECE_EMAIL',
    passwordEnv: 'ECE_PASSWORD',
    defaultUrl: 'https://ece.open-webui.myia.io',
  },
  esg: {
    urlEnv: 'ESG_URL',
    emailEnv: 'ESG_EMAIL',
    passwordEnv: 'ESG_PASSWORD',
    defaultUrl: 'https://esg.open-webui.myia.io',
  },
  epita: {
    urlEnv: 'EPITA_URL',
    emailEnv: 'EPITA_EMAIL',
    passwordEnv: 'EPITA_PASSWORD',
    defaultUrl: 'https://epita.open-webui.myia.io',
  },
  pauwels: {
    urlEnv: 'PAUWELS_URL',
    emailEnv: 'PAUWELS_EMAIL',
    passwordEnv: 'PAUWELS_PASSWORD',
    defaultUrl: 'https://pauwels.open-webui.myia.io',
  },
};

/**
 * Get the configuration for a specific tenant.
 * Throws if email/password are not set in environment.
 */
export function getTenantConfig(tenantName: string): TenantConfig {
  const tenant = TENANTS[tenantName];
  if (!tenant) {
    throw new Error(`Unknown tenant: ${tenantName}. Available: ${Object.keys(TENANTS).join(', ')}`);
  }

  const url = process.env[tenant.urlEnv] || tenant.defaultUrl;
  const email = process.env[tenant.emailEnv];
  const password = process.env[tenant.passwordEnv];

  if (!email || !password) {
    throw new Error(
      `Missing credentials for tenant "${tenantName}". ` +
      `Set ${tenant.emailEnv} and ${tenant.passwordEnv} in .env`
    );
  }

  return { name: tenantName, url, email, password };
}

/**
 * Detect which tenant this test run targets based on Playwright project name.
 * Falls back to 'myia' if not determinable.
 */
export function getTenantFromProjectName(projectName: string): string {
  // Project names: 'myia', 'epf', 'myia-setup', 'epf-setup'
  return projectName.replace('-setup', '');
}
