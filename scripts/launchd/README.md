# EDU Apps LaunchDaemon - Auto-Start Without Login

This LaunchDaemon enables the EDU Apps servers to start automatically at system boot, **without requiring any user to log in**.

## Why LaunchDaemon?

- **LaunchAgents** only run when a user is logged in
- **LaunchDaemons** run at system boot, regardless of user login
- Perfect for headless servers like macmini

## Files

| File | Purpose |
|------|---------|
| `com.eduapps.servers.plist` | LaunchDaemon configuration |
| `install_daemon.sh` | Installation script (requires sudo) |
| `uninstall_daemon.sh` | Uninstallation script (requires sudo) |

## Prerequisites

1. The startup script must exist on macmini:
   ```bash
   # As server user on macmini:
   cat > ~/start_edu_servers.sh << 'EOF'
   #!/bin/bash
   export PATH=~/homebrew/bin:$PATH
   sleep 5
   lsof -i :5051 -t | xargs kill -9 2>/dev/null
   lsof -i :5052 -t | xargs kill -9 2>/dev/null
   lsof -i :5063 -t | xargs kill -9 2>/dev/null
   sleep 2
   tmux kill-session -t dev 2>/dev/null
   tmux kill-session -t qa 2>/dev/null
   tmux kill-session -t prod 2>/dev/null
   tmux new-session -d -s dev  "source ~/.tcshrc; edu-dev"
   tmux new-session -d -s qa   "source ~/.tcshrc; edu-qa"
   tmux new-session -d -s prod "source ~/.tcshrc; edu-prod"
   echo "EDU Apps started at $(date)" >> ~/edu_startup.log
   EOF
   chmod +x ~/start_edu_servers.sh
   ```

2. tmux must be installed (already done via homebrew)

3. .tcshrc with aliases must be configured (already done)

## Installation (Requires Admin Access)

SSH to macmini as an **admin user** (e.g., jgirmay or hatsibha):

```bash
# Copy files to macmini
scp -r launchd/ macmini:~/

# SSH to macmini as admin user
ssh jgirmay@macmini

# Install the daemon
sudo ~/launchd/install_daemon.sh
```

## Manual Installation

If the script doesn't work, install manually:

```bash
# As admin user on macmini:
sudo cp ~/launchd/com.eduapps.servers.plist /Library/LaunchDaemons/
sudo chown root:wheel /Library/LaunchDaemons/com.eduapps.servers.plist
sudo chmod 644 /Library/LaunchDaemons/com.eduapps.servers.plist
sudo launchctl load /Library/LaunchDaemons/com.eduapps.servers.plist
```

## Commands

| Command | Description |
|---------|-------------|
| `sudo launchctl start com.eduapps.servers` | Start servers now |
| `sudo launchctl stop com.eduapps.servers` | Stop servers |
| `sudo launchctl list \| grep eduapps` | Check status |
| `sudo launchctl unload /Library/LaunchDaemons/com.eduapps.servers.plist` | Disable auto-start |

## Logs

- Startup log: `/Users/server/edu_daemon.log`
- Error log: `/Users/server/edu_daemon_error.log`
- Server logs: `/tmp/dev.log`, `/tmp/qa.log`, `/tmp/prod.log`

## Uninstall

```bash
sudo ~/launchd/uninstall_daemon.sh
```

Or manually:
```bash
sudo launchctl unload /Library/LaunchDaemons/com.eduapps.servers.plist
sudo rm /Library/LaunchDaemons/com.eduapps.servers.plist
```
