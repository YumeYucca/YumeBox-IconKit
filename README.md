# YumeBox-IconKit

Build custom YumeBox icon APKs with GitHub Actions.

Use the [YumeBox custom icon tool](https://yumebox.gal.tf/guide/icon-builder) to create an icon and start a build, then open the linked GitHub Actions run to download the build artifact.

## Operations

Configure the R2 cleanup rule once from an environment authenticated for the
Cloudflare account. It deletes uploaded job metadata and icon bundles under
`jobs/` after one day, including abandoned uploads that are never requested.

```bash
npm run r2:lifecycle
```

The build workflow creates these GitHub labels on its first IconKit Issue:
`iconkit: pending`, `approved`, `iconkit: building`, `iconkit: success`,
`iconkit: failed`, and `iconkit: rate-limited`. After passing the rate-limit
check, the workflow adds `approved` and starts the build automatically. A user
who creates five IconKit Issues in one hour is rate limited for four hours.
The repository owner and `YumeYuka` are exempt from this user limit.
