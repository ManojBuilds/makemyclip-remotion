import fs from 'fs';
import path from 'path';

// Simple .env parser
function loadEnv() {
  const envPath = path.resolve('.env');
  if (!fs.existsSync(envPath)) return;
  const content = fs.readFileSync(envPath, 'utf8');
  for (const line of content.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const parts = trimmed.split('=');
    if (parts.length >= 2) {
      const key = parts[0].trim();
      const val = parts.slice(1).join('=').trim().replace(/^"(.*)"$/, '$1').replace(/^'(.*)'$/, '$1');
      process.env[key] = val;
    }
  }
}

loadEnv();

const url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ';
const downloaderEndpoint = process.env.MODAL_YT_DOWNLOADER_ENDPOINT;
const metadataEndpoint = process.env.MODAL_YT_METADATA_ENDPOINT || 
  (downloaderEndpoint ? downloaderEndpoint.replace("-download.modal.run", "-metadata.modal.run") : null);

console.log('MODAL_YT_DOWNLOADER_ENDPOINT:', downloaderEndpoint);
console.log('Computed metadataEndpoint:', metadataEndpoint);

if (!metadataEndpoint) {
  console.error('Metadata endpoint not resolved!');
  process.exit(1);
}

console.log('Sending request to metadataEndpoint...');
fetch(metadataEndpoint, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ url }),
})
  .then(res => {
    console.log('Response status:', res.status);
    return res.json();
  })
  .then(data => {
    console.log('Response data:', data);
    if (data.success && data.duration === 213) {
      console.log('TEST PASSED! Success:', data.success, 'Duration:', data.duration);
    } else {
      console.error('TEST FAILED: Unexpected response structure or values');
    }
  })
  .catch(err => {
    console.error('TEST ERROR:', err);
  });
