Write-Host "Initializing Git repository..." -ForegroundColor Green
git init

Write-Host "Adding all files..." -ForegroundColor Green
git add .

Write-Host "Setting up Git configuration..." -ForegroundColor Green
git config user.name "kemel222"
git config user.email "kemelyt222@gmail.com"

Write-Host "Committing files..." -ForegroundColor Green
git commit -m "Initial commit: HotSpot Shop - Full Telegram Bot & Web App"

Write-Host "Setting main branch..." -ForegroundColor Green
git branch -M main

Write-Host "Adding remote origin..." -ForegroundColor Green
git remote add origin https://github.com/kemel222/telegram-shop-backend-bot.git

Write-Host "Pushing to GitHub..." -ForegroundColor Green
git push -u origin main

Write-Host "Done! Repository uploaded successfully." -ForegroundColor Green
Read-Host "Press Enter to continue"
