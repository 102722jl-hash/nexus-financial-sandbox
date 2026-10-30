$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m unittest -v test_v2_pipeline.py test_parsers.py test_company_announcements.py test_announcement_discovery.py test_nce_public.py test_remaining.py
