# Vendored front-end libraries

| File | Package | Version | License | Source |
|------|---------|---------|---------|--------|
| `vis-network.min.js` | vis-network | 9.1.9 | Apache-2.0 / MIT | https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js |

SHA-256 of `vis-network.min.js`:

```
f53f833ddb9bf97efe856bb0637d4fe88f39e39999c7e94a4b8afc8de8a1a2e5
```

`build_catalog_site.py` copies these files into `docs/catalog/vendor/` on each generate.
Do not load vis-network from an unpinned CDN in the generated page.
