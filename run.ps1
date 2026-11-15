# Windows: fresh demo data for both restaurants, then the app.   Run:  .\run.ps1
# The shipped demo invoices are dated 2026-11-15 (judging day). To use another date: $env:LOBSTA_TODAY = "2026-11-14"
if (-not $env:LOBSTA_TODAY) { $env:LOBSTA_TODAY = "2026-11-15" }
python -m scripts.seed_demo --profile sushi  --today $env:LOBSTA_TODAY
python -m scripts.seed_demo --profile hotpot --today $env:LOBSTA_TODAY
Write-Host "`nPhone page:     http://<this laptop's wifi IP>:8080/   (ipconfig shows it)"
Write-Host "Projector page: http://localhost:8080/sheet`n"
python -m uvicorn app.server:app --host 0.0.0.0 --port 8080
