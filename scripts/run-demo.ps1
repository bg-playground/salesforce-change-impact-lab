$ErrorActionPreference = "Stop"
python tools/impact_lab.py --metadata tests/fixtures/baseline/High_Discount_Requires_Finance.validationRule-meta.xml --contract policies/SF-OPP-001.json --json-out evidence/baseline-report.json --html-out evidence/baseline-report.html
python tools/impact_lab.py --metadata mutations/High_Discount_Requires_Finance.threshold-30.validationRule-meta.xml --contract policies/SF-OPP-001.json --json-out evidence/mutation-report.json --html-out evidence/mutation-report.html
if ($LASTEXITCODE -ne 2) { throw "Expected mutant to be rejected with exit code 2; got $LASTEXITCODE" }
Write-Host "PASS: isolated baseline accepted and semantic mutant rejected."
exit 0
