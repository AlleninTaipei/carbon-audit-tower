// Carbon Audit Control Tower — dev server
// Reads GOOGLE_MAPS_API_KEY from environment and injects it at request time.
// Never writes the key into any source file.
//
// Run (Node >= 20.6):  node --env-file=.env server.js
// Run (older Node):    GOOGLE_MAPS_API_KEY=AIza... node server.js

const http = require('http');
const fs   = require('fs');
const path = require('path');

const KEY  = process.env.GOOGLE_MAPS_API_KEY;
const PORT = process.env.PORT || 3000;
const HTML = path.join(__dirname, 'audit-control-tower.html');

if (!KEY || KEY === 'YOUR_KEY_HERE') {
  console.error('');
  console.error('  ❌  GOOGLE_MAPS_API_KEY 未設定');
  console.error('  請在 .env 填入真實的 API Key 後重新啟動');
  console.error('');
  process.exit(1);
}

http.createServer((req, res) => {
  if (req.url !== '/') {
    res.writeHead(404);
    res.end('Not found');
    return;
  }
  try {
    const html = fs.readFileSync(HTML, 'utf8').replace('YOUR_API_KEY', KEY);
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(html);
  } catch (e) {
    res.writeHead(500);
    res.end(e.message);
  }
}).listen(PORT, () => {
  console.log('');
  console.log('  ✅  Carbon Audit Control Tower');
  console.log(`  →   http://localhost:${PORT}`);
  console.log('');
});
