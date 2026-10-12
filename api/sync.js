// Vercel serverless function: the page's "Sync leads now" button calls POST /api/sync,
// which starts the GitHub Actions workflow .github/workflows/sync.yml.
// Vercel env vars: GH_TOKEN (fine-grained token, this repo, "Actions: Read and write"),
//                  GH_REPO ("owner/repo"), GH_BRANCH (default "main").
module.exports = async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'POST only' });
    return;
  }
  const repo = process.env.GH_REPO;
  const token = process.env.GH_TOKEN;
  if (!repo || !token) {
    res.status(500).json({ error: 'GH_REPO / GH_TOKEN not set in Vercel' });
    return;
  }
  const r = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/sync.yml/dispatches`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ ref: process.env.GH_BRANCH || 'main' })
  });
  if (r.status === 204) {
    res.status(200).json({ ok: true });
    return;
  }
  res.status(502).json({ error: `GitHub ${r.status}: ${(await r.text()).slice(0, 300)}` });
};
