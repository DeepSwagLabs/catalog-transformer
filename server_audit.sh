#!/bin/bash
# Server Audit Script for trunk1.creativemerch.com
# Run this after SSH'ing in to understand the system
#
# Usage: bash server_audit.sh > audit_results.txt 2>&1

echo "=== Creative Merchandise Server Audit ==="
echo "Date: $(date)"
echo "Hostname: $(hostname)"
echo ""

echo "=== OS Information ==="
cat /etc/os-release 2>/dev/null || cat /etc/*-release 2>/dev/null
uname -a
echo ""

echo "=== Web Server ==="
which apache2 httpd nginx 2>/dev/null
apache2 -v 2>/dev/null || httpd -v 2>/dev/null || nginx -v 2>/dev/null
echo ""

echo "=== PHP Version ==="
php -v 2>/dev/null
echo ""

echo "=== MySQL/MariaDB ==="
which mysql mysqld mariadb 2>/dev/null
mysql --version 2>/dev/null
echo ""

echo "=== Web Root Candidates ==="
ls -la /var/www/ 2>/dev/null
ls -la /var/www/html/ 2>/dev/null
ls -la /home/*/public_html/ 2>/dev/null
echo ""

echo "=== Apache/Nginx Config ==="
cat /etc/apache2/sites-enabled/*.conf 2>/dev/null | head -50
cat /etc/httpd/conf.d/*.conf 2>/dev/null | head -50
cat /etc/nginx/sites-enabled/* 2>/dev/null | head -50
echo ""

echo "=== Database Config Candidates ==="
echo "Looking for config files with DB credentials..."
find /var/www -name "*.php" -exec grep -l "mysql_connect\|mysqli\|PDO.*mysql\|DB_HOST\|DB_PASS" {} \; 2>/dev/null | head -20
echo ""

echo "=== Cron Jobs ==="
crontab -l 2>/dev/null
ls -la /etc/cron.d/ 2>/dev/null
echo ""

echo "=== Disk Usage ==="
df -h
echo ""
du -sh /var/www/* 2>/dev/null
du -sh /home/* 2>/dev/null
echo ""

echo "=== Large Files (>100MB) ==="
find /var/www /home -size +100M -exec ls -lh {} \; 2>/dev/null | head -20
echo ""

echo "=== Recent Log Activity ==="
ls -lt /var/log/*.log 2>/dev/null | head -10
echo ""

echo "=== MySQL Databases (if accessible) ==="
mysql -e "SHOW DATABASES;" 2>/dev/null
echo ""

echo "=== Done ==="
echo "Copy this output and share it for analysis."
