# Third-party software and SDK inventory

This inventory records the direct Python packages declared or imported by this project. Package versions are not locked to exact builds in the repository. Each Windows release workflow therefore generates a `THIRD_PARTY_LICENSES.md` report from the actual build environment, listing resolved package versions, licence identifiers and upstream URLs, including transitive dependencies.

## Runtime dependencies

| Package | Purpose in this project | Upstream licence |
|---|---|---|
| CustomTkinter | Desktop interface widgets | MIT — https://github.com/TomSchimansky/CustomTkinter/blob/master/LICENSE |
| Pillow | Local image and icon processing | MIT-CMU — https://github.com/python-pillow/Pillow/blob/main/LICENSE |
| certifi | TLS certificate bundle | MPL-2.0 — https://github.com/certifi/python-certifi/blob/master/LICENSE |

## Additional Market Insight dependencies

| Package | Purpose in this project | Upstream licence |
|---|---|---|
| yfinance | Retrieve market data from Yahoo Finance's public interfaces | Apache-2.0 — https://github.com/ranaroussi/yfinance/blob/main/LICENSE.txt |
| pandas | Market-data analysis and tabular calculations | BSD-3-Clause — https://github.com/pandas-dev/pandas/blob/main/LICENSE |
| requests | HTTPS requests to data providers | Apache-2.0 — https://github.com/psf/requests/blob/main/LICENSE |
| keyring | Store Alpaca credentials in the operating-system credential store | MIT — https://github.com/jaraco/keyring/blob/main/LICENSE |
| tzdata | Time-zone database support | Apache-2.0 — https://github.com/python/tzdata/blob/master/LICENSE |

## Build tooling

PyInstaller is used by the Windows release workflow to package the desktop application. Its licence is GPL-2.0 with a bootloader exception, with additional files under Apache-2.0 as described by the upstream project: https://github.com/pyinstaller/pyinstaller/blob/develop/doc/license.rst

## Website SDK and tracking review

The website source was reviewed for external script imports, embedded frames, analytics tags, advertising pixels and third-party JavaScript SDKs. None were found in the main project pages reviewed. Inline project scripts provide interface behaviour and, where applicable, request public release metadata from GitHub. This is a source review, not a guarantee about future third-party behaviour.

## Release checklist

Before each public release:
- Review the generated `THIRD_PARTY_LICENSES.md` report for unknown, changed or restrictive licences.
- Check the exact licence text and required attribution for all direct and transitive dependencies.
- Confirm the packaged distribution includes the upstream licence files required by those dependencies.
- Re-run the SDK and network-endpoint review when dependencies or update/data integrations change.
