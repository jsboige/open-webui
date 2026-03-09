// Deploy v3 avatars to OWUI models via API
// Usage: node scripts/deploy_avatars_v3.cjs <base_url> <email> <password>
const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

const tmpDir = process.env.TEMP || 'C:\\Users\\MYIA\\AppData\\Local\\Temp';

const avatarMap = {
  'expert-analyste': path.join(tmpDir, 'avatar_analyste_v3.json'),
  'redacteur-technique': path.join(tmpDir, 'avatar_redacteur_v3.json'),
  'vision-expert': path.join(tmpDir, 'avatar_vision_v3.json'),
  'Local.qwen3.5-35b-a3b-fast': path.join(tmpDir, 'avatar_fast_v3.json'),
};

function request(url, method, headers, body) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const mod = u.protocol === 'https:' ? https : http;
    const opts = {
      hostname: u.hostname,
      port: u.port || (u.protocol === 'https:' ? 443 : 80),
      path: u.pathname + u.search,
      method,
      headers,
      rejectUnauthorized: false,
    };
    const req = mod.request(opts, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({ status: res.statusCode, body: data }));
    });
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

async function main() {
  const baseUrl = process.argv[2];
  const email = process.argv[3];
  const password = process.argv[4];

  if (!baseUrl || !email || !password) {
    console.error('Usage: node deploy_avatars_v3.cjs <base_url> <email> <password>');
    process.exit(1);
  }

  const authRes = await request(`${baseUrl}/api/v1/auths/signin`, 'POST',
    { 'Content-Type': 'application/json' },
    JSON.stringify({ email, password }));
  const token = JSON.parse(authRes.body).token;
  if (!token) { console.error(`  AUTH FAILED for ${baseUrl}`); return; }
  console.log(`  Authenticated to ${baseUrl}`);

  const authHeaders = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  for (const [modelId, jsonFile] of Object.entries(avatarMap)) {
    const sdData = JSON.parse(fs.readFileSync(jsonFile, 'utf8'));
    const b64 = sdData.images[0];
    const dataUrl = `data:image/png;base64,${b64}`;

    const getRes = await request(`${baseUrl}/api/v1/models/model?id=${encodeURIComponent(modelId)}`, 'GET', authHeaders);
    if (getRes.status !== 200) {
      console.log(`  ${modelId}: NOT FOUND (HTTP ${getRes.status}), skipping`);
      continue;
    }

    const model = JSON.parse(getRes.body);
    model.meta = model.meta || {};
    model.meta.profile_image_url = dataUrl;

    const updateRes = await request(`${baseUrl}/api/v1/models/model/update`, 'POST', authHeaders, JSON.stringify(model));
    console.log(`  ${modelId}: avatar updated (${(b64.length/1024).toFixed(0)} KB) -> HTTP ${updateRes.status}`);
  }
}

main().catch(e => console.error(e));
