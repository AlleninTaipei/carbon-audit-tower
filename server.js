// Carbon Audit Control Tower — dev server
// 注入：GOOGLE_MAPS_API_KEY（從 .env）+ Pipeline 輸出資料（從 data/output/）
//
// Run (Node >= 20.6):  node --env-file=.env server.js
// Run (older Node):    GOOGLE_MAPS_API_KEY=AIza... node server.js

const http = require('http');
const fs   = require('fs');
const path = require('path');

const KEY       = process.env.GOOGLE_MAPS_API_KEY;
const PORT      = process.env.PORT || 3000;
const HTML_FILE = path.join(__dirname, 'audit-control-tower.html');
const DATA_FILE = path.join(__dirname, 'data', 'output', 'carbon_audit_records.json');

if (!KEY || KEY === 'YOUR_KEY_HERE') {
  console.error('\n  ❌  GOOGLE_MAPS_API_KEY 未設定');
  console.error('  請在 .env 填入真實的 API Key 後重新啟動\n');
  process.exit(1);
}

if (!fs.existsSync(DATA_FILE)) {
  console.error('\n  ❌  找不到 Pipeline 輸出：data/output/carbon_audit_records.json');
  console.error('  請先執行：python3 data/run_pipeline.py\n');
  process.exit(1);
}

const server = http.createServer((req, res) => {
  if (req.url !== '/') { res.writeHead(404); res.end('Not found'); return; }

  try {
    const pipelineData = fs.readFileSync(DATA_FILE, 'utf8');
    const html = fs.readFileSync(HTML_FILE, 'utf8')
      .replace('YOUR_API_KEY',      KEY)
      .replace('__PIPELINE_DATA__', pipelineData);

    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(html);
  } catch (e) {
    res.writeHead(500);
    res.end(e.message);
  }
});

server.listen(PORT, () => {
  const data = JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
  const totalCo2 = data.reduce((s, r) => s + (r.co2 || 0), 0);

  console.log('');
  console.log('  ✅  Carbon Audit Control Tower');
  console.log(`  →   http://localhost:${PORT}`);
  console.log(`  →   資料：${data.length} 筆運單 · 總碳排 ${Math.round(totalCo2).toLocaleString()} kg CO₂e`);
  console.log('');
});

function shutdown(signal) {
  console.log(`\n  🛑  收到 ${signal}，伺服器關閉中…`);
  server.close(() => {
    console.log('  ✅  已安全關閉\n');
    process.exit(0);
  });
}

process.on('SIGINT',  () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));
