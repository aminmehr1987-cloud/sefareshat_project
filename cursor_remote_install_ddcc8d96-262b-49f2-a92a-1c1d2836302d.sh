
echo "Configuring Cursor Server on Remote"


SERVER_COMMIT="5c17eb2968a37f66bc6662f48d6356a100b67be0"
SERVER_REAL_COMMIT="5c17eb2968a37f66bc6662f48d6356a100b67be8"
SERVER_LINE="production"
SERVER_DATA_DIR="$HOME/.cursor-server"
PORT_RANGE=""

# Probe for writable temporary directory
probe_tmp_dir() {
    if [[ -n "${XDG_RUNTIME_DIR}" && -d "${XDG_RUNTIME_DIR}" ]]; then
        local test_file="${XDG_RUNTIME_DIR}/cursor-test-$(date +%s)-$RANDOM"
        if touch "$test_file" 2>/dev/null && [[ -f "$test_file" ]]; then
            rm -f "$test_file"
            echo "${XDG_RUNTIME_DIR}"
            return 0
        fi
    fi
    if [[ -d "/tmp" ]]; then
        local test_file="/tmp/cursor-test-$(date +%s)-$RANDOM"
        if touch "$test_file" 2>/dev/null && [[ -f "$test_file" ]]; then
            rm -f "$test_file"
            echo "/tmp"
            return 0
        fi
    fi
    echo "$SERVER_DATA_DIR"  # fallback
}

TMP_DIR="$(probe_tmp_dir)"
echo "Using TMP_DIR: $TMP_DIR"
SERVER_DIR="$SERVER_DATA_DIR/bin/5c17eb2968a37f66bc6662f48d6356a100b67be0"
SERVER_NODE_EXECUTABLE="$SERVER_DIR/node"
CODE_SERVER_SCRIPT="$SERVER_DIR/bin/cursor-server"
CODE_SERVER_PROCESS_ALL_VERSIONS_GREP_PATTERN="$SERVER_DATA_DIR/bin/.*/out/server-main.js"
CODE_LISTENING_ON=
CODE_SERVER_CONNECTION_TOKEN=
MULTIPLEX_SERVER_SCRIPT="$SERVER_DATA_DIR/bin/multiplex-server/3ce73d09cffc8f33c6d911e972bd0f6dabbe3e26e810844be8060e6b10987db8.js"
MULTIPLEX_LISTENING_ON=
SERVER_ARCH=
SERVER_DOWNLOAD_URL=
OS_RELEASE_ID=
ARCH=
PLATFORM=
export PATH="$SERVER_DIR/bin/remote-cli:$PATH"

get_tmp_file() {
    local suffix=$1
    echo "$TMP_DIR/cursor-remote-${suffix}.$(echo $SERVER_DATA_DIR | (md5sum 2>/dev/null || md5) | awk '{print $1}')"
}

get_tmp_file_with_hash() {
    local suffix=$1
    local hash=$2
    echo "$TMP_DIR/cursor-remote-${suffix}.$(echo $SERVER_DATA_DIR | (md5sum 2>/dev/null || md5) | awk '{print $1}').${hash}"
}



CODE_SERVER_LOGFILE="$(get_tmp_file 'code.log')"
CODE_SERVER_TOKENFILE="$(get_tmp_file 'code.token')"
CODE_SERVER_PIDFILE="$(get_tmp_file 'code.pid')"
MULTIPLEX_SERVER_LOGFILE="$(get_tmp_file_with_hash 'multiplex.log' '3ce73d09cffc8f33c6d911e972bd0f6dabbe3e26e810844be8060e6b10987db8')"
MULTIPLEX_SERVER_TOKENFILE="$(get_tmp_file_with_hash 'multiplex.token' '3ce73d09cffc8f33c6d911e972bd0f6dabbe3e26e810844be8060e6b10987db8')"
MULTIPLEX_SERVER_PIDFILE="$(get_tmp_file_with_hash 'multiplex.pid' '3ce73d09cffc8f33c6d911e972bd0f6dabbe3e26e810844be8060e6b10987db8')"
MULTIPLEX_SERVER_PROCESS_ALL_VERSIONS_GREP_PATTERN="$SERVER_DATA_DIR/bin/multiplex-server/.*.js"

# These are magic variables that are used by the code server
export VSCODE_AGENT_FOLDER="$SERVER_DATA_DIR"
export VSCODE_SERVER_SHUTDOWN_TIMEOUT="300"

# If the SSH_AUTH_SOCK is set, we symlink it to a well-known location based on the SSH_AUTH_SOCK_ID
# This is because terminals and other parts of the editor don't update to use the latest SSH_AUTH_SOCK
if [[ -n "$SSH_AUTH_SOCK" ]]; then
    if [[ -n "/tmp/cursor-remote-ssh-auth-sock-eed25d59-ee4a-46e6-9921-11a5201a24e8.sock" ]]; then
        ln -sf "$SSH_AUTH_SOCK" "/tmp/cursor-remote-ssh-auth-sock-eed25d59-ee4a-46e6-9921-11a5201a24e8.sock"
        export SSH_AUTH_SOCK="/tmp/cursor-remote-ssh-auth-sock-eed25d59-ee4a-46e6-9921-11a5201a24e8.sock"
    fi
fi

print_install_results_and_exit() {
    echo "4f013f2c99e96dab197026a8: start"
    echo "exitCode==$1=="
    echo "nodeExecutable==$SERVER_NODE_EXECUTABLE=="
    echo "multiplexListeningOn==$MULTIPLEX_LISTENING_ON=="
    echo "multiplexConnectionToken==$MULTIPLEX_SERVER_CONNECTION_TOKEN=="
    echo "codeListeningOn==$CODE_LISTENING_ON=="
    echo "errorMessage==$2=="
    echo "isFatalError==$3=="
    echo "codeConnectionToken==$CODE_SERVER_CONNECTION_TOKEN=="
    echo "detectedPlatform==$PLATFORM=="
    echo "arch==$SERVER_ARCH=="
    echo "SSH_AUTH_SOCK==$SSH_AUTH_SOCK=="
    echo "4f013f2c99e96dab197026a8: end"
    exit $1
}

print_install_results_and_wait() {
    # Try to get PIDs from PID files first, fallback to extracting from running processes
    if [[ -f $CODE_SERVER_PIDFILE ]]; then
        CODE_SERVER_PID="$(cat $CODE_SERVER_PIDFILE)"
    else
        # PID file doesn't exist, try to extract PID from running process
        CODE_SERVER_RUNNING_PROCESS="$(ps -o pid,args -A | grep $CODE_SERVER_SCRIPT | grep -v grep | head -1)"
        if [[ -n "$CODE_SERVER_RUNNING_PROCESS" ]]; then
            CODE_SERVER_PID="$(echo "$CODE_SERVER_RUNNING_PROCESS" | awk '{print $1}')"
        else
            print_install_results_and_exit 1 "Code server PID file not found and no running code server process detected" "false"
        fi
    fi

    if [[ -f $MULTIPLEX_SERVER_PIDFILE ]]; then
        MULTIPLEX_SERVER_PID="$(cat $MULTIPLEX_SERVER_PIDFILE)"
    else
        # PID file doesn't exist, try to extract PID from running process
        MULTIPLEX_SERVER_RUNNING_PROCESS="$(ps -o pid,args -A | grep $MULTIPLEX_SERVER_SCRIPT | grep -v grep | head -1)"
        if [[ -n "$MULTIPLEX_SERVER_RUNNING_PROCESS" ]]; then
            MULTIPLEX_SERVER_PID="$(echo "$MULTIPLEX_SERVER_RUNNING_PROCESS" | awk '{print $1}')"
        else
            echo "Multiplex server PID file not found and no running multiplex server process detected"
            # This pid doesn't exist, so the while loop will exit immediately
            MULTIPLEX_SERVER_PID=invalid_pid
        fi
    fi

    echo "4f013f2c99e96dab197026a8: start"
    echo "exitCode==0=="
    echo "nodeExecutable==$SERVER_NODE_EXECUTABLE=="
    echo "errorMessage===="
    echo "isFatalError==false=="
    echo "multiplexListeningOn==$MULTIPLEX_LISTENING_ON=="
    echo "multiplexConnectionToken==$MULTIPLEX_SERVER_CONNECTION_TOKEN=="
    echo "codeListeningOn==$CODE_LISTENING_ON=="
    echo "codeConnectionToken==$CODE_SERVER_CONNECTION_TOKEN=="
    echo "detectedPlatform==$PLATFORM=="
    echo "arch==$SERVER_ARCH=="
    echo "SSH_AUTH_SOCK==$SSH_AUTH_SOCK=="
    echo "4f013f2c99e96dab197026a8: end"
    unlock
    trap - EXIT
    echo " "
    echo "***********************************************************************"
    echo "* This terminal is used to establish and maintain the SSH connection. *"
    echo "* Closing this terminal will terminate the connection and disconnect  *"
    echo "* Cursor from the remote server.                                      *"
    echo "***********************************************************************"
    # We need to wait for both servers to exit -- when using docker over ssh, the code server won't have a connection
    while kill -0 $CODE_SERVER_PID 2>/dev/null
    do
        sleep 10
    done
    echo "Code server process $CODE_SERVER_PID died"
    while kill -0 $MULTIPLEX_SERVER_PID 2>/dev/null
    do
        sleep 11
    done
    echo "Multiplex server process $MULTIPLEX_SERVER_PID died"
    exit 0
}

get_lockfile() {
    echo "$TMP_DIR/cursor-remote-lock.$(echo $SERVER_DATA_DIR | (md5sum 2>/dev/null || md5) | awk '{print $1}')"
}

if [[ "false" == "true" ]]; then
    echo "Killing all running Cursor servers"
    CODE_SERVER_RUNNING_PROCESS="$(ps -o pid,args -A | grep $CODE_SERVER_PROCESS_ALL_VERSIONS_GREP_PATTERN | grep -v grep || true)"
    if [[ -z "$CODE_SERVER_RUNNING_PROCESS" ]]; then
        echo "No running code servers found"
    fi
    echo "Killing running code servers: $CODE_SERVER_RUNNING_PROCESS"
    echo "$CODE_SERVER_RUNNING_PROCESS" | while read -r line; do
        pid=$(echo "$line" | awk '{print $1}')
        if [[ -n "$pid" ]]; then
            echo "Killing server process with PID: $pid"
            kill -9 "$pid"
        fi
    done
    CODE_SERVER_RUNNING_PROCESS=""
    echo "Killing all running multiplex servers"
    MULTIPLEX_SERVER_RUNNING_PROCESS="$(ps -o pid,args -A | grep $MULTIPLEX_SERVER_PROCESS_ALL_VERSIONS_GREP_PATTERN | grep -v grep || true)"
    if [[ -z "$MULTIPLEX_SERVER_RUNNING_PROCESS" ]]; then
        echo "No running multiplex servers found"
    fi
    echo "Killing running multiplex servers: $MULTIPLEX_SERVER_RUNNING_PROCESS"
    echo "$MULTIPLEX_SERVER_RUNNING_PROCESS" | while read -r line; do
        pid=$(echo "$line" | awk '{print $1}')
        if [[ -n "$pid" ]]; then
            echo "Killing server process with PID: $pid"
            kill -9 "$pid"
        fi
    done
    MULTIPLEX_SERVER_RUNNING_PROCESS=""
fi

if [[ 'false' == "true" ]]; then
    echo "Removing all existing Cursor installations"
    rm -rf "$SERVER_DATA_DIR/bin"         $SERVER_DATA_DIR/.*.code.log         $SERVER_DATA_DIR/.*.code.pid         $SERVER_DATA_DIR/.*.code.token         $SERVER_DATA_DIR/.*.multiplex.pid         $SERVER_DATA_DIR/.*.multiplex.token         $SERVER_DATA_DIR/.*.multiplex.log         $SERVER_DATA_DIR/.*.pid         $SERVER_DATA_DIR/.*.token         $SERVER_DATA_DIR/.*.log         $(get_lockfile)         $(get_lockfile).target         $(get_tmp_file 'code.log')         $(get_tmp_file 'code.pid')         $(get_tmp_file 'code.token')         $(get_tmp_file_with_hash 'multiplex.log' '3ce73d09cffc8f33c6d911e972bd0f6dabbe3e26e810844be8060e6b10987db8')         $(get_tmp_file_with_hash 'multiplex.pid' '3ce73d09cffc8f33c6d911e972bd0f6dabbe3e26e810844be8060e6b10987db8')         $(get_tmp_file_with_hash 'multiplex.token' '3ce73d09cffc8f33c6d911e972bd0f6dabbe3e26e810844be8060e6b10987db8')

    # Don't delete the server we just copied
    echo "Deleting left behind cursor servers, except for $HOME/.cursor-server/cursor-server-a433d107-6bc7-487f-93b4-3e722faef1c1.tar.gz"
    find "$SERVER_DATA_DIR" -name "cursor-server-*.tar.gz" ! -name "$(basename $HOME/.cursor-server/cursor-server-a433d107-6bc7-487f-93b4-3e722faef1c1.tar.gz)" -delete -print
    echo "Done deleting left behind cursor servers"
fi

unlock() {
    lockfile=$(get_lockfile)
    if [ -n "$LOCK_PID" ]; then
        kill $LOCK_PID 2>/dev/null
    fi
    echo "Unlocking $lockfile"
    rm -f "$lockfile"
    rm -f "$lockfile.target"
}

lock() {
    lockfile=$(get_lockfile)
    echo "Locking $lockfile"
    lockAcquired=0
    for i in {1..30}; do
        if [ -f "$lockfile" ]; then
            # Check if lock is stale (older than 10 seconds)
            current_time=$(date +%s)
            lock_time=$(cat "$lockfile" 2>/dev/null || echo 0)
            if [ $((current_time - lock_time)) -gt 10 ]; then
                echo "Found stale lock, removing..."
                rm -f "$lockfile"
            fi
        fi
        touch "$lockfile.target"
        ln "$lockfile.target" "$lockfile"
        if [ $? -eq 0 ]; then
            lockAcquired=1
            # Start a background process to update timestamp
            # Locking for at most 15 minutes (900 seconds) -- really bad to having processes dangling forever
            counter=0
            while [ $counter -lt 900 ]; do
                date +%s > "$lockfile"
                sleep 1
                counter=$((counter + 1))
            done &
            LOCK_PID=$!
            break
        fi
        echo "Install in progress, sleeping for a bit..."
        sleep 1
    done
    if [ $lockAcquired -eq 0 ]; then
        print_install_results_and_exit 1 "Could not acquire lock after multiple attempts"
    fi
    trap unlock EXIT
}

KERNEL="$(uname -s)"
case $KERNEL in
    Darwin)
        PLATFORM="darwin"
        ;;
    Linux)
        PLATFORM="linux"
        ;;
    FreeBSD)
        PLATFORM="linux"
        ;;
    *)
        print_install_results_and_exit 1 "Platform not supported: $KERNEL" "true"
        ;;
esac

ARCH="$(uname -m)"
case $ARCH in
    x86_64 | amd64)
        SERVER_ARCH="x64"
        ;;
    arm64 | aarch64)
        SERVER_ARCH="arm64"
        ;;
    *)
        print_install_results_and_exit 1 "Architecture not supported: $ARCH" "true"
        ;;
esac

OS_RELEASE_ID="$(grep -i '^ID=' /etc/os-release 2>/dev/null | sed 's/^ID=//gi' | sed 's/"//g')"
if [[ -z $OS_RELEASE_ID ]]; then
    OS_RELEASE_ID="$(grep -i '^ID=' /usr/lib/os-release 2>/dev/null | sed 's/^ID=//gi' | sed 's/"//g')"
    if [[ -z $OS_RELEASE_ID ]]; then
        OS_RELEASE_ID="unknown"
    fi
fi

# Create installation folder
mkdir -p $SERVER_DIR
if (( $? > 0 )); then
    print_install_results_and_exit 1 "Error creating server install directory $SERVER_DIR"
fi

# adjust platform for alpine (musl-libc based binary) download, if needed
if [[ $OS_RELEASE_ID = alpine ]]; then
    PLATFORM=$OS_RELEASE_ID
fi
SERVER_DOWNLOAD_URL="$(echo "https://downloads.cursor.com/\${line}/\${realCommit}/\${platform}/\${arch}/cursor-reh-\${platform}-\${arch}.tar.gz" | sed "s/\${line}/$SERVER_LINE/g" | sed "s/\${realCommit}/$SERVER_REAL_COMMIT/g"  | sed "s/\${commit}/$SERVER_COMMIT/g" | sed "s/\${platform}/$PLATFORM/g" | sed "s/\${arch}/$SERVER_ARCH/g")"
lock
# Check if server script is already installed
if [[ ! -f $CODE_SERVER_SCRIPT ]]; then
    pushd $SERVER_DIR > /dev/null
    RANDOM_FILENAME="cursor-server-69c22968-fcc9-4432-b70b-9974754e3141.tar.gz"
    if [[ -f "$HOME/.cursor-server/cursor-server-a433d107-6bc7-487f-93b4-3e722faef1c1.tar.gz" ]]; then
        echo "Found existing server archive at $HOME/.cursor-server/cursor-server-a433d107-6bc7-487f-93b4-3e722faef1c1.tar.gz, using it instead of downloading"
        mv "$HOME/.cursor-server/cursor-server-a433d107-6bc7-487f-93b4-3e722faef1c1.tar.gz" $RANDOM_FILENAME
    else
        if [[ 'false' == 'true' ]]; then
            echo "Server not found at $HOME/.cursor-server/cursor-server-a433d107-6bc7-487f-93b4-3e722faef1c1.tar.gz, and local download is required"
            print_install_results_and_exit 1 "Download failed: Failed to copy server from local client" "true"
        fi
        if [[ ! -z $(which wget) ]]; then
            echo "Downloading server via wget from $SERVER_DOWNLOAD_URL to $RANDOM_FILENAME"
            # Use fancy progress bar when supported (GNU Wget). Fall back if not.
            if wget --help 2>&1 | grep -q -- '--progress='; then
                WGET_PROGRESS='--progress=bar:force:noscroll'
            else
                WGET_PROGRESS='--progress=dot'
            fi
            wget --tries=2 --timeout=5 --continue $WGET_PROGRESS -O $RANDOM_FILENAME $SERVER_DOWNLOAD_URL
        elif [[ ! -z $(which curl) ]]; then
            echo "Downloading server via curl from $SERVER_DOWNLOAD_URL to $RANDOM_FILENAME"
            curl --retry 2 --fail --connect-timeout 5 --location --progress-bar --output $RANDOM_FILENAME $SERVER_DOWNLOAD_URL
        else
            print_install_results_and_exit 1 "Download failed: Error no tool to download server binary. Please install wget or curl" "true"
        fi
        if (( $? > 0 )); then
            if [[ "$OS_RELEASE_ID" == 'alpine' && 'false' = 'true' ]]; then
                # Only showing this error if the download actually fails, and we know that the version is pre-Alpine
                # Don't want the download to fail if it actually would have worked!
                print_install_results_and_exit 1 "Please update Cursor to the latest version to connect to Alpine-based remote servers" "true"
            fi
            print_install_results_and_exit 1 "Download failed: Error downloading server from $SERVER_DOWNLOAD_URL" "false"
        fi
    fi
    echo "Extracting server contents from $RANDOM_FILENAME"
    tar -xf $RANDOM_FILENAME --strip-components 1
    if (( $? > 0 )); then
        print_install_results_and_exit 1 "Tar failed to extract server contents from $RANDOM_FILENAME" "false"
    fi
    if [[ ! -f $CODE_SERVER_SCRIPT ]]; then
        print_install_results_and_exit 1 "Failed to extract code server script: $CODE_SERVER_SCRIPT" "false"
    fi
    rm -f $RANDOM_FILENAME
    popd > /dev/null
else
    echo "Server script already installed in $CODE_SERVER_SCRIPT"
fi
echo "Checking node executable"
if ! $SERVER_NODE_EXECUTABLE --version; then
    echo "Node executable at $SERVER_NODE_EXECUTABLE is not working, checking system node"
    SYSTEM_NODE=$(which node)
    if [[ -n "$SYSTEM_NODE" ]]; then
        echo "System node version: $($SYSTEM_NODE --version)"
        $SYSTEM_NODE -e "process.exit(parseInt(process.version.slice(1)) >= 20 ? 0 : 1)"
        if [[ $? -eq 0 ]]; then
            echo "System node version is 20 or higher, creating symlink"
            ln -sf $SYSTEM_NODE $SERVER_NODE_EXECUTABLE
            echo "Created symlink from $SERVER_NODE_EXECUTABLE to $SYSTEM_NODE"
        else
            print_install_results_and_exit 1 "The bundled NodeJS failed to run, and system node is too old. Please manually install NodeJS 20 or higher on your remote system" "true"
        fi
    else
        print_install_results_and_exit 1 "The bundled NodeJS failed to run, and no system NodeJS executable was found. Please manually install NodeJS 20 or higher on your remote system" "true"
    fi
fi

# Clean up stale builds
OLD_COMMITS=$(ls -1 -t "$SERVER_DATA_DIR/bin" | tail -n +6)
for OLD_COMMIT in $OLD_COMMITS; do
    IS_RUNNING=`ps ax | grep $OLD_COMMIT | grep -v grep | wc -l | tr -d '[:space:]'`
    if [[ $IS_RUNNING -eq 0 ]]; then
        echo "Cleaning up stale build $OLD_COMMIT"
        if [[ "$OLD_COMMIT" != "$SERVER_COMMIT" ]]; then
            rm -rf "$SERVER_DATA_DIR/bin/$OLD_COMMIT" "$SERVER_DATA_DIR/.$OLD_COMMIT.*"
        fi
    else
        echo "Build $OLD_COMMIT is still running, skipping"
    fi
done

# Symlink $SERVER_DIR/bin/remote-cli/code -> $SERVER_DIR/bin/remote-cli/cursor (force)
REMOTE_CLI_DIR="$SERVER_DIR/bin/remote-cli"
if [ -d "$REMOTE_CLI_DIR" ]; then
    ln -sf cursor "$REMOTE_CLI_DIR/code"
fi

# Try to find if server is already running
echo "Checking for running multiplex server: $MULTIPLEX_SERVER_SCRIPT"
if [[ -f $MULTIPLEX_SERVER_PIDFILE ]]; then
    MULTIPLEX_SERVER_PID="$(cat $MULTIPLEX_SERVER_PIDFILE)"
    MULTIPLEX_SERVER_RUNNING_PROCESS="$(ps -o pid,args -A | grep -w $MULTIPLEX_SERVER_PID | grep $MULTIPLEX_SERVER_SCRIPT)"
else
    MULTIPLEX_SERVER_RUNNING_PROCESS="$(ps -o pid,args -A | grep $MULTIPLEX_SERVER_SCRIPT | grep -v grep)"
fi
echo "Running multiplex server: $MULTIPLEX_SERVER_RUNNING_PROCESS"

if [[ -z $MULTIPLEX_SERVER_RUNNING_PROCESS || ! -f $MULTIPLEX_SERVER_LOGFILE || ! -f $MULTIPLEX_SERVER_TOKENFILE ]]; then
    if [[ -f $MULTIPLEX_SERVER_LOGFILE ]]; then
        rm $MULTIPLEX_SERVER_LOGFILE
    fi
    if [[ -f $MULTIPLEX_SERVER_TOKENFILE ]]; then
        rm $MULTIPLEX_SERVER_TOKENFILE
    fi

    echo "Creating multiplex server token file $MULTIPLEX_SERVER_TOKENFILE"
    touch $MULTIPLEX_SERVER_TOKENFILE
    chmod 600 $MULTIPLEX_SERVER_TOKENFILE
    MULTIPLEX_SERVER_CONNECTION_TOKEN="68a15c54-4204-40ec-b5e8-08f26c814260"
    echo $MULTIPLEX_SERVER_CONNECTION_TOKEN > $MULTIPLEX_SERVER_TOKENFILE

    # This is super counterintuitive, but we UNSET the SSH_AUTH_SOCK before starting the server, because we manually inject it into the extension host later.
    # This is to prevent us from being used across ALL connections by default

    # Backing it up, NOT exporting it
    if [[ -n "$SSH_AUTH_SOCK" ]]; then
        ORIGINAL_SSH_AUTH_SOCK=$SSH_AUTH_SOCK
        unset SSH_AUTH_SOCK
    fi

    echo "Creating directory for multiplex server: $(dirname $MULTIPLEX_SERVER_SCRIPT)"
    mkdir -p $(dirname "$MULTIPLEX_SERVER_SCRIPT")
    echo "Writing multiplex server script to $MULTIPLEX_SERVER_SCRIPT"
    echo 'InVzZSBzdHJpY3QiO3ZhciBfX2Fzc2lnbj10aGlzJiZ0aGlzLl9fYXNzaWdufHxmdW5jdGlvbigpe3JldHVybiBfX2Fzc2lnbj1PYmplY3QuYXNzaWdufHxmdW5jdGlvbihlKXtmb3IodmFyIHIsdD0xLG49YXJndW1lbnRzLmxlbmd0aDt0PG47dCsrKWZvcih2YXIgbyBpbiByPWFyZ3VtZW50c1t0XSlPYmplY3QucHJvdG90eXBlLmhhc093blByb3BlcnR5LmNhbGwocixvKSYmKGVbb109cltvXSk7cmV0dXJuIGV9LF9fYXNzaWduLmFwcGx5KHRoaXMsYXJndW1lbnRzKX0sX19hd2FpdGVyPXRoaXMmJnRoaXMuX19hd2FpdGVyfHxmdW5jdGlvbihlLHIsdCxuKXtyZXR1cm4gbmV3KHR8fCh0PVByb21pc2UpKSgoZnVuY3Rpb24obyxpKXtmdW5jdGlvbiBjKGUpe3RyeXtzKG4ubmV4dChlKSl9Y2F0Y2goZSl7aShlKX19ZnVuY3Rpb24gYShlKXt0cnl7cyhuLnRocm93KGUpKX1jYXRjaChlKXtpKGUpfX1mdW5jdGlvbiBzKGUpe3ZhciByO2UuZG9uZT9vKGUudmFsdWUpOihyPWUudmFsdWUsciBpbnN0YW5jZW9mIHQ/cjpuZXcgdCgoZnVuY3Rpb24oZSl7ZShyKX0pKSkudGhlbihjLGEpfXMoKG49bi5hcHBseShlLHJ8fFtdKSkubmV4dCgpKX0pKX0sX19nZW5lcmF0b3I9dGhpcyYmdGhpcy5fX2dlbmVyYXRvcnx8ZnVuY3Rpb24oZSxyKXt2YXIgdCxuLG8saT17bGFiZWw6MCxzZW50OmZ1bmN0aW9uKCl7aWYoMSZvWzBdKXRocm93IG9bMV07cmV0dXJuIG9bMV19LHRyeXM6W10sb3BzOltdfSxjPU9iamVjdC5jcmVhdGUoKCJmdW5jdGlvbiI9PXR5cGVvZiBJdGVyYXRvcj9JdGVyYXRvcjpPYmplY3QpLnByb3RvdHlwZSk7cmV0dXJuIGMubmV4dD1hKDApLGMudGhyb3c9YSgxKSxjLnJldHVybj1hKDIpLCJmdW5jdGlvbiI9PXR5cGVvZiBTeW1ib2wmJihjW1N5bWJvbC5pdGVyYXRvcl09ZnVuY3Rpb24oKXtyZXR1cm4gdGhpc30pLGM7ZnVuY3Rpb24gYShhKXtyZXR1cm4gZnVuY3Rpb24ocyl7cmV0dXJuIGZ1bmN0aW9uKGEpe2lmKHQpdGhyb3cgbmV3IFR5cGVFcnJvcigiR2VuZXJhdG9yIGlzIGFscmVhZHkgZXhlY3V0aW5nLiIpO2Zvcig7YyYmKGM9MCxhWzBdJiYoaT0wKSksaTspdHJ5e2lmKHQ9MSxuJiYobz0yJmFbMF0/bi5yZXR1cm46YVswXT9uLnRocm93fHwoKG89bi5yZXR1cm4pJiZvLmNhbGwobiksMCk6bi5uZXh0KSYmIShvPW8uY2FsbChuLGFbMV0pKS5kb25lKXJldHVybiBvO3N3aXRjaChuPTAsbyYmKGE9WzImYVswXSxvLnZhbHVlXSksYVswXSl7Y2FzZSAwOmNhc2UgMTpvPWE7YnJlYWs7Y2FzZSA0OnJldHVybiBpLmxhYmVsKysse3ZhbHVlOmFbMV0sZG9uZTohMX07Y2FzZSA1OmkubGFiZWwrKyxuPWFbMV0sYT1bMF07Y29udGludWU7Y2FzZSA3OmE9aS5vcHMucG9wKCksaS50cnlzLnBvcCgpO2NvbnRpbnVlO2RlZmF1bHQ6aWYoISgobz0obz1pLnRyeXMpLmxlbmd0aD4wJiZvW28ubGVuZ3RoLTFdKXx8NiE9PWFbMF0mJjIhPT1hWzBdKSl7aT0wO2NvbnRpbnVlfWlmKDM9PT1hWzBdJiYoIW98fGFbMV0+b1swXSYmYVsxXTxvWzNdKSl7aS5sYWJlbD1hWzFdO2JyZWFrfWlmKDY9PT1hWzBdJiZpLmxhYmVsPG9bMV0pe2kubGFiZWw9b1sxXSxvPWE7YnJlYWt9aWYobyYmaS5sYWJlbDxvWzJdKXtpLmxhYmVsPW9bMl0saS5vcHMucHVzaChhKTticmVha31vWzJdJiZpLm9wcy5wb3AoKSxpLnRyeXMucG9wKCk7Y29udGludWV9YT1yLmNhbGwoZSxpKX1jYXRjaChlKXthPVs2LGVdLG49MH1maW5hbGx5e3Q9bz0wfWlmKDUmYVswXSl0aHJvdyBhWzFdO3JldHVybnt2YWx1ZTphWzBdP2FbMV06dm9pZCAwLGRvbmU6ITB9fShbYSxzXSl9fX07T2JqZWN0LmRlZmluZVByb3BlcnR5KGV4cG9ydHMsIl9fZXNNb2R1bGUiLHt2YWx1ZTohMH0pO3ZhciBuZXRfMT1yZXF1aXJlKCJuZXQiKSxjaGlsZF9wcm9jZXNzXzE9cmVxdWlyZSgiY2hpbGRfcHJvY2VzcyIpLGNyeXB0b18xPXJlcXVpcmUoImNyeXB0byIpLHRva2VuPXByb2Nlc3MuYXJndlsyXTt0b2tlbnx8KGNvbnNvbGUuZXJyb3IoIlRva2VuIG11c3QgYmUgcHJvdmlkZWQgYXMgdGhlIGZpcnN0IGFyZ3VtZW50IikscHJvY2Vzcy5leGl0KDEpKTt2YXIgcG9ydEFyZz1wcm9jZXNzLmFyZ3ZbM118fCIwIixwb3J0PTA7ZnVuY3Rpb24gcGFyc2VQb3J0UmFuZ2UoZSl7aWYoIjAiPT09ZXx8IiI9PT1lKXJldHVybiAwO3ZhciByPWUubWF0Y2goL14oXGQrKS0oXGQrKSQvKTtpZihyKXt2YXIgdD1wYXJzZUludChyWzFdLDEwKSxuPXBhcnNlSW50KHJbMl0sMTApO3JldHVybiB0Pj1uJiYoY29uc29sZS5lcnJvcigiSW52YWxpZCBwb3J0IHJhbmdlOiAiLmNvbmNhdChlLCIuIFN0YXJ0IHBvcnQgbXVzdCBiZSBsZXNzIHRoYW4gZW5kIHBvcnQuIikpLHByb2Nlc3MuZXhpdCgxKSksKHQ8MXx8bj42NTUzNSkmJihjb25zb2xlLmVycm9yKCJJbnZhbGlkIHBvcnQgcmFuZ2U6ICIuY29uY2F0KGUsIi4gUG9ydHMgbXVzdCBiZSBiZXR3ZWVuIDEgYW5kIDY1NTM1LiIpKSxwcm9jZXNzLmV4aXQoMSkpLHtzdGFydDp0LGVuZDpufX12YXIgbz1wYXJzZUludChlLDEwKTtyZXR1cm4oaXNOYU4obyl8fG88MHx8bz42NTUzNSkmJihjb25zb2xlLmVycm9yKCJJbnZhbGlkIHBvcnQ6ICIuY29uY2F0KGUpKSxwcm9jZXNzLmV4aXQoMSkpLG99ZnVuY3Rpb24gZmluZEZyZWVQb3J0SW5SYW5nZShlLHIpe3JldHVybiBfX2F3YWl0ZXIodGhpcyx2b2lkIDAsdm9pZCAwLChmdW5jdGlvbigpe3ZhciB0LG4sbyxpO3JldHVybiBfX2dlbmVyYXRvcih0aGlzLChmdW5jdGlvbihjKXtzd2l0Y2goYy5sYWJlbCl7Y2FzZSAwOnQ9cmVxdWlyZSgibmV0Iiksbj1mdW5jdGlvbihlKXtyZXR1cm4gX19nZW5lcmF0b3IodGhpcywoZnVuY3Rpb24ocil7c3dpdGNoKHIubGFiZWwpe2Nhc2UgMDpyZXR1cm4gci50cnlzLnB1c2goWzAsMiwsM10pLFs0LG5ldyBQcm9taXNlKChmdW5jdGlvbihyLG4pe3ZhciBvPXQuY3JlYXRlU2VydmVyKCk7by5saXN0ZW4oZSwiMTI3LjAuMC4xIiwoZnVuY3Rpb24oKXtvLmNsb3NlKCkscigpfSkpLm9uKCJlcnJvciIsKGZ1bmN0aW9uKCl7bigpfSkpfSkpXTtjYXNlIDE6cmV0dXJuIHIuc2VudCgpLFsyLHt2YWx1ZTplfV07Y2FzZSAyOnJldHVybiByLnNlbnQoKSxbMywzXTtjYXNlIDM6cmV0dXJuWzJdfX0pKX0sbz1lLGMubGFiZWw9MTtjYXNlIDE6cmV0dXJuIG88PXI/WzUsbihvKV06WzMsNF07Y2FzZSAyOmlmKCJvYmplY3QiPT10eXBlb2YoaT1jLnNlbnQoKSkpcmV0dXJuWzIsaS52YWx1ZV07Yy5sYWJlbD0zO2Nhc2UgMzpyZXR1cm4gbysrLFszLDFdO2Nhc2UgNDp0aHJvdyBuZXcgRXJyb3IoIk5vIGZyZWUgcG9ydCBmb3VuZCBpbiByYW5nZSAiLmNvbmNhdChlLCItIikuY29uY2F0KHIpKX19KSl9KSl9ZnVuY3Rpb24gaW5pdGlhbGl6ZVBvcnQoKXtyZXR1cm4gX19hd2FpdGVyKHRoaXMsdm9pZCAwLHZvaWQgMCwoZnVuY3Rpb24oKXt2YXIgZSxyLHQ7cmV0dXJuIF9fZ2VuZXJhdG9yKHRoaXMsKGZ1bmN0aW9uKG4pe3N3aXRjaChuLmxhYmVsKXtjYXNlIDA6cmV0dXJuIm51bWJlciIhPXR5cGVvZihlPXBhcnNlUG9ydFJhbmdlKHBvcnRBcmcpKT9bMywxXTpbMixlXTtjYXNlIDE6cmV0dXJuIG4udHJ5cy5wdXNoKFsxLDMsLDRdKSxbNCxmaW5kRnJlZVBvcnRJblJhbmdlKGUuc3RhcnQsZS5lbmQpXTtjYXNlIDI6cmV0dXJuIHI9bi5zZW50KCksY29uc29sZS5sb2coIkZvdW5kIGZyZWUgcG9ydCAiLmNvbmNhdChyLCIgaW4gcmFuZ2UgIikuY29uY2F0KGUuc3RhcnQsIi0iKS5jb25jYXQoZS5lbmQpKSxbMixyXTtjYXNlIDM6cmV0dXJuIHQ9bi5zZW50KCksY29uc29sZS5lcnJvcigiRmFpbGVkIHRvIGZpbmQgZnJlZSBwb3J0OiAiLmNvbmNhdCh0KSkscHJvY2Vzcy5leGl0KDEpLFszLDRdO2Nhc2UgNDpyZXR1cm5bMl19fSkpfSkpfXZhciBERUZBVUxUX1NIVVRET1dOX1RJTUVPVVRfTVM9M2U1LFNIVVRET1dOX1RJTUVPVVRfTVM9REVGQVVMVF9TSFVURE9XTl9USU1FT1VUX01TO3Byb2Nlc3MuZW52LlZTQ09ERV9TRVJWRVJfU0hVVERPV05fVElNRU9VVCYmKFNIVVRET1dOX1RJTUVPVVRfTVM9MWUzKnBhcnNlSW50KHByb2Nlc3MuZW52LlZTQ09ERV9TRVJWRVJfU0hVVERPV05fVElNRU9VVCwxMCksaXNOYU4oU0hVVERPV05fVElNRU9VVF9NUykmJihjb25zb2xlLmVycm9yKCJJbnZhbGlkIFZTQ09ERV9TRVJWRVJfU0hVVERPV05fVElNRU9VVDogIi5jb25jYXQocHJvY2Vzcy5lbnYuVlNDT0RFX1NFUlZFUl9TSFVURE9XTl9USU1FT1VUKSksU0hVVERPV05fVElNRU9VVF9NUz1ERUZBVUxUX1NIVVRET1dOX1RJTUVPVVRfTVMpKTt2YXIgaW5hY3Rpdml0eVRpbWVyLHNlcnZlcj0oMCxuZXRfMS5jcmVhdGVTZXJ2ZXIpKHtrZWVwQWxpdmU6ITB9LChmdW5jdGlvbihlKXtjb25zb2xlLmxvZygiU2VydmVyIHJlY2VpdmVkIGNvbm5lY3Rpb24iKSxyZXNldEluYWN0aXZpdHlUaW1lcigpO3ZhciByLHQsbj1CdWZmZXIuYWxsb2MoMCk7ZS5vbigiY2xvc2UiLChmdW5jdGlvbigpe2NvbnNvbGUubG9nKCJbcmVtb3RlU2VydmVyXVsiLmNvbmNhdCh0LCJdIFNvY2tldCBjbG9zZWQ7IGtpbGxpbmcgY2hpbGQgcHJvY2VzcyIpKSxyJiZyLnBpZCYmIXIua2lsbGVkJiYoKG51bGw9PXI/dm9pZCAwOnIua2lsbCgpKXx8Y29uc29sZS5lcnJvcigiW3JlbW90ZVNlcnZlcl1bIi5jb25jYXQodCwiXSBGYWlsZWQgdG8ga2lsbCBjaGlsZCBwcm9jZXNzIikpKX0pKSxlLm9uKCJkYXRhIiwoZnVuY3Rpb24obyl7dmFyIGksYyxhO2lmKG49QnVmZmVyLmNvbmNhdChbbixvXSksdm9pZCAwPT09cil7dmFyIHM9bi5pbmRleE9mKEJ1ZmZlci5mcm9tKCJcbiIpKTtpZigtMT09PXMpcmV0dXJuO3ZhciBsPW4uc3ViYXJyYXkoMCxzKS50b1N0cmluZygpO249bi5zdWJhcnJheShzKzEpO3ZhciB1PXZvaWQgMDt0cnl7dT1KU09OLnBhcnNlKGwpfWNhdGNoKHIpe3JldHVybiBjb25zb2xlLmVycm9yKCJFcnJvciBwYXJzaW5nIEpTT04gY29tbWFuZDoiLHIpLHZvaWQgZS5kZXN0cm95KCl9aWYodS50b2tlbiE9PXRva2VuKXJldHVybiBjb25zb2xlLmVycm9yKCJJbnZhbGlkIHRva2VuOiIsdS50b2tlbiksZS53cml0ZShKU09OLnN0cmluZ2lmeSh7dHlwZToiZXhpdCIsY29kZTo0MDF9KSsiXG4iKSx2b2lkIGUuZW5kKCk7dD1udWxsIT09KGk9dS5pZCkmJnZvaWQgMCE9PWk/aTooMCxjcnlwdG9fMS5yYW5kb21VVUlEKSgpLGNvbnNvbGUubG9nKCJbY29tbWFuZF1bIi5jb25jYXQodCwiXSBFeGVjdXRpbmcgY29tbWFuZDogIikuY29uY2F0KHUuY29tbWFuZCwiICIpLmNvbmNhdCgobnVsbCE9PShjPXUuYXJncykmJnZvaWQgMCE9PWM/YzpbXSkuam9pbigiICIpKSksKHI9KDAsY2hpbGRfcHJvY2Vzc18xLnNwYXduKSh1LmNvbW1hbmQsbnVsbCE9PShhPXUuYXJncykmJnZvaWQgMCE9PWE/YTpbXSx7ZW52Ol9fYXNzaWduKF9fYXNzaWduKHt9LHByb2Nlc3MuZW52KSx1LmVudiksY3dkOnUuY3dkLHNoZWxsOiExLHN0ZGlvOiJwaXBlIn0pKS5zdGRvdXQub24oImRhdGEiLChmdW5jdGlvbihyKXt2YXIgdD17dHlwZToic3Rkb3V0IixkYXRhOnIudG9TdHJpbmcoImJhc2U2NCIpfTtlLndyaXRlKEpTT04uc3RyaW5naWZ5KHQpKyJcbiIpfSkpLHIuc3Rkb3V0Lm9uKCJlbmQiLChmdW5jdGlvbigpe2Uud3JpdGUoSlNPTi5zdHJpbmdpZnkoe3R5cGU6InN0ZG91dC1lbmQifSkrIlxuIil9KSksci5zdGRlcnIub24oImRhdGEiLChmdW5jdGlvbihyKXt2YXIgdD17dHlwZToic3RkZXJyIixkYXRhOnIudG9TdHJpbmcoImJhc2U2NCIpfTtlLndyaXRlKEpTT04uc3RyaW5naWZ5KHQpKyJcbiIpfSkpLHIuc3RkZXJyLm9uKCJlbmQiLChmdW5jdGlvbigpe2Uud3JpdGUoSlNPTi5zdHJpbmdpZnkoe3R5cGU6InN0ZGVyci1lbmQifSkrIlxuIil9KSk7dmFyIGQ9ITE7ci5vbigiZXJyb3IiLChmdW5jdGlvbihyKXtkP2NvbnNvbGUubG9nKCJbY29tbWFuZF1bIi5jb25jYXQodCwiXSBQcm9jZXNzIGV4aXRlZCB3aXRoIGVycm9yIGJ1dCB3ZSBhbHJlYWR5IHNlbnQgYW4gZXhpdCBtZXNzYWdlIikscik6KGQ9ITAsY29uc29sZS5lcnJvcigiW2NvbW1hbmRdWyIuY29uY2F0KHQsIl0gUHJvY2VzcyBlcnJvciIpLHIpLGUud3JpdGUoSlNPTi5zdHJpbmdpZnkoe3R5cGU6ImV4aXQiLGNvZGU6MX0pKyJcbiIpLGUuZW5kKCkpfSkpLHIub24oImV4aXQiLChmdW5jdGlvbihyKXtpZihkKWNvbnNvbGUubG9nKCJbY29tbWFuZF1bIi5jb25jYXQodCwiXSBQcm9jZXNzIGV4aXRlZCB3aXRoIGNvZGUgIikuY29uY2F0KHIsIiBidXQgd2UgYWxyZWFkeSBzZW50IGFuIGV4aXQgbWVzc2FnZSIpKTtlbHNle2Q9ITAsY29uc29sZS5sb2coIltjb21tYW5kXVsiLmNvbmNhdCh0LCJdIFByb2Nlc3MgZXhpdGVkIHdpdGggY29kZSAiKS5jb25jYXQociwiLiBTZW5kaW5nIGV4aXQgbWVzc2FnZSIpKTt2YXIgbj17dHlwZToiZXhpdCIsY29kZTpudWxsIT09cj9yOjB9O2Uud3JpdGUoSlNPTi5zdHJpbmdpZnkobikrIlxuIiksZS5lbmQoKX19KSl9dmFyIGY9bi5pbmRleE9mKDApO2lmKC0xIT09Zil7dmFyIHA9bi5zdWJhcnJheSgwLGYpO3RyeXt2YXIgdj1CdWZmZXIuZnJvbShwLnRvU3RyaW5nKCJ1dGYtOCIpLCJiYXNlNjQiKTtyLnN0ZGluLndyaXRlKHYpfWNhdGNoKHQpe3JldHVybiBjb25zb2xlLmVycm9yKCJFcnJvciBkZWNvZGluZyBiYXNlNjQgZGF0YToiLHQpLGUuZGVzdHJveSgpLHZvaWQgci5raWxsKCJTSUdLSUxMIil9cmV0dXJuIHIuc3RkaW4uZW5kKCksdm9pZChuPUJ1ZmZlci5hbGxvYygwKSl9dmFyIF89NCpNYXRoLmZsb29yKG4ubGVuZ3RoLzQpO2lmKDAhPT1fKXt2YXIgZz1uLnN1YmFycmF5KDAsXyk7bj1uLnN1YmFycmF5KF8pO3RyeXt2PUJ1ZmZlci5mcm9tKGcudG9TdHJpbmcoInV0Zi04IiksImJhc2U2NCIpLHIuc3RkaW4ud3JpdGUodil9Y2F0Y2godCl7cmV0dXJuIGNvbnNvbGUuZXJyb3IoIkVycm9yIGRlY29kaW5nIGJhc2U2NCBkYXRhOiIsdCksci5raWxsKCJTSUdLSUxMIiksdm9pZCBlLmRlc3Ryb3koKX19fSkpLGUub24oImVycm9yIiwoZnVuY3Rpb24oZSl7Y29uc29sZS5lcnJvcigiW3JlbW90ZVNlcnZlcl1bIi5jb25jYXQodCwiXSBTb2NrZXQgZXJyb3I6IiksZSksciYmci5raWxsKCJTSUdLSUxMIil9KSl9KSk7ZnVuY3Rpb24gcmVzZXRJbmFjdGl2aXR5VGltZXIoKXtpbmFjdGl2aXR5VGltZXImJmNsZWFyVGltZW91dChpbmFjdGl2aXR5VGltZXIpLGluYWN0aXZpdHlUaW1lcj1zZXRUaW1lb3V0KChmdW5jdGlvbigpe2NvbnNvbGUuZXJyb3IoIk5vIGNvbm5lY3Rpb25zIHJlY2VpdmVkIGZvciAiLmNvbmNhdChTSFVURE9XTl9USU1FT1VUX01TLzFlMywiIHNlY29uZHMsIHNodXR0aW5nIGRvd24uLi4iKSkscHJvY2Vzcy5leGl0KDApfSksU0hVVERPV05fVElNRU9VVF9NUyl9cmVzZXRJbmFjdGl2aXR5VGltZXIoKSxpbml0aWFsaXplUG9ydCgpLnRoZW4oKGZ1bmN0aW9uKGUpe3BvcnQ9ZSxzZXJ2ZXIubGlzdGVuKHtob3N0OiIxMjcuMC4wLjEiLHBvcnR9LChmdW5jdGlvbigpe3ZhciBlPXNlcnZlci5hZGRyZXNzKCk7bnVsbD09PWUmJihjb25zb2xlLmVycm9yKCJGYWlsZWQgdG8gZ2V0IHNlcnZlciBhZGRyZXNzIikscHJvY2Vzcy5leGl0KDEpKSwic3RyaW5nIj09dHlwZW9mIGUmJihjb25zb2xlLmVycm9yKCJJbnZhbGlkIGFkZHJlc3M6ICIuY29uY2F0KGUpKSxwcm9jZXNzLmV4aXQoMSkpLGNvbnNvbGUubG9nKCJTZXJ2ZXIgbGlzdGVuaW5nIG9uICIuY29uY2F0KGUucG9ydCkpfSkpfSkpLmNhdGNoKChmdW5jdGlvbihlKXtjb25zb2xlLmVycm9yKCJGYWlsZWQgdG8gaW5pdGlhbGl6ZSBwb3J0OiIsZSkscHJvY2Vzcy5leGl0KDEpfSkpLHByb2Nlc3Mub24oIlNJR0lOVCIsKGZ1bmN0aW9uKCl7c2VydmVyLmNsb3NlKChmdW5jdGlvbigpe2NvbnNvbGUubG9nKCJTZXJ2ZXIgY2xvc2VkIikscHJvY2Vzcy5leGl0KDApfSkpfSkpOw==' | (base64 -d 2>/dev/null || base64 -D) > "$MULTIPLEX_SERVER_SCRIPT"

    # Pass the port range directly to multiplex server (or empty string for OS selection)
    MULTIPLEX_SERVER_PORT_ARG="${PORT_RANGE:-0}"

    echo "Starting multiplex server: $SERVER_NODE_EXECUTABLE $MULTIPLEX_SERVER_SCRIPT $MULTIPLEX_SERVER_CONNECTION_TOKEN $MULTIPLEX_SERVER_PORT_ARG"
    $SERVER_NODE_EXECUTABLE "$MULTIPLEX_SERVER_SCRIPT" "$MULTIPLEX_SERVER_CONNECTION_TOKEN" "$MULTIPLEX_SERVER_PORT_ARG" &> $MULTIPLEX_SERVER_LOGFILE &
    echo $! > $MULTIPLEX_SERVER_PIDFILE
    echo "Multiplex server started with PID $(cat $MULTIPLEX_SERVER_PIDFILE) and wrote pid to file $MULTIPLEX_SERVER_PIDFILE"

    # Restoring the original SSH_AUTH_SOCK
    if [[ -n "$ORIGINAL_SSH_AUTH_SOCK" ]]; then
        export SSH_AUTH_SOCK=$ORIGINAL_SSH_AUTH_SOCK
        unset ORIGINAL_SSH_AUTH_SOCK
    fi
else
    echo "Multiplex server script is already running $MULTIPLEX_SERVER_SCRIPT. Running processes are $MULTIPLEX_SERVER_RUNNING_PROCESS"
fi

echo "Reading multiplex server token file $MULTIPLEX_SERVER_TOKENFILE"

if [[ -f $MULTIPLEX_SERVER_TOKENFILE ]]; then
    echo "Multiplex server token file found"
    MULTIPLEX_SERVER_CONNECTION_TOKEN="$(cat $MULTIPLEX_SERVER_TOKENFILE)"
else
    print_install_results_and_exit 1 "Multiplex server token file not found: $MULTIPLEX_SERVER_TOKENFILE"
fi

echo "Reading multiplex server log file $MULTIPLEX_SERVER_LOGFILE"

for i in {1..180}; do
    if [[ -f $MULTIPLEX_SERVER_LOGFILE ]]; then
        MULTIPLEX_LISTENING_ON="$(cat $MULTIPLEX_SERVER_LOGFILE | grep -E 'Server listening on .+' | sed 's/Server listening on //')"
        if [[ -n "$MULTIPLEX_LISTENING_ON" ]]; then
            break
        fi
    fi
    sleep 0.5
done

if [[ -z "$MULTIPLEX_LISTENING_ON" ]]; then
    echo "Error multiplex server did not start successfully. Below are the logs"
    # Reading the logfile, to help with debugging
    ls -al $MULTIPLEX_SERVER_LOGFILE || true
    cat $MULTIPLEX_SERVER_LOGFILE || true
fi


echo "Checking for code servers"
if [[ -f $CODE_SERVER_PIDFILE ]]; then
    CODE_SERVER_PID="$(cat $CODE_SERVER_PIDFILE)"
    CODE_SERVER_RUNNING_PROCESS="$(ps -o pid,args -A | grep -w $CODE_SERVER_PID | grep $CODE_SERVER_SCRIPT)"
else
    CODE_SERVER_RUNNING_PROCESS="$(ps -o pid,args -A | grep $CODE_SERVER_SCRIPT | grep -v grep)"
fi

# Making sure the token file and log files exists; otherwise we need to start a new server
if [[ -z $CODE_SERVER_RUNNING_PROCESS || ! -f $CODE_SERVER_TOKENFILE || ! -f $CODE_SERVER_LOGFILE ]]; then
    echo "Code server script is not running"
    if [[ -f $CODE_SERVER_LOGFILE ]]; then
        rm $CODE_SERVER_LOGFILE
    fi
    if [[ -f $CODE_SERVER_TOKENFILE ]]; then
        rm $CODE_SERVER_TOKENFILE
    fi

    echo "Creating code server token file $CODE_SERVER_TOKENFILE"
    touch $CODE_SERVER_TOKENFILE
    chmod 600 $CODE_SERVER_TOKENFILE
    CODE_SERVER_CONNECTION_TOKEN="90c7287f-859e-4b7c-a0b6-cec627f06e15"
    echo $CODE_SERVER_CONNECTION_TOKEN > $CODE_SERVER_TOKENFILE

    # This is super counterintuitive, but we UNSET the SSH_AUTH_SOCK before starting the server, because we manually inject it into the extension host later.
    # This is to prevent us from being used across ALL connections by default

    # Backing it up, NOT exporting it
    if [[ -n "$SSH_AUTH_SOCK" ]]; then
        ORIGINAL_SSH_AUTH_SOCK=$SSH_AUTH_SOCK
        unset SSH_AUTH_SOCK
    fi

    # Pass the port range directly to code server (or 0 for OS selection)
    CODE_SERVER_PORT_ARG="${PORT_RANGE:-0}"

    echo "Starting code server script $CODE_SERVER_SCRIPT --start-server --host=127.0.0.1 --port $CODE_SERVER_PORT_ARG  --connection-token-file $CODE_SERVER_TOKENFILE --telemetry-level off --enable-remote-auto-shutdown --accept-server-license-terms &> $CODE_SERVER_LOGFILE &"

    $CODE_SERVER_SCRIPT --start-server --host=127.0.0.1 --port $CODE_SERVER_PORT_ARG  --connection-token-file $CODE_SERVER_TOKENFILE --telemetry-level off --enable-remote-auto-shutdown --accept-server-license-terms &> $CODE_SERVER_LOGFILE &
    echo $! > $CODE_SERVER_PIDFILE
    echo "Code server started with PID $(cat $CODE_SERVER_PIDFILE) and wrote pid to file $CODE_SERVER_PIDFILE"

    # Restoring the original SSH_AUTH_SOCK
    if [[ -n "$ORIGINAL_SSH_AUTH_SOCK" ]]; then
        export SSH_AUTH_SOCK=$ORIGINAL_SSH_AUTH_SOCK
        unset ORIGINAL_SSH_AUTH_SOCK
    fi
else
    echo "Code server script is already running $CODE_SERVER_SCRIPT. Running processes are $CODE_SERVER_RUNNING_PROCESS"
fi

if [[ -f $CODE_SERVER_TOKENFILE ]]; then
    CODE_SERVER_CONNECTION_TOKEN="$(cat $CODE_SERVER_TOKENFILE)"
else
    print_install_results_and_exit 1 "Code server token file not found: $CODE_SERVER_TOKENFILE"
fi

echo "Code server log file is $CODE_SERVER_LOGFILE"
for i in {1..180}; do
    if [[ -f $CODE_SERVER_LOGFILE ]]; then
        CODE_LISTENING_ON="$(cat $CODE_SERVER_LOGFILE | grep -E 'Extension host agent listening on .+' | sed 's/Extension host agent listening on //')"
        if [[ -n "$CODE_LISTENING_ON" ]]; then
            break
        fi
    fi
    sleep 0.5
done

if [[ -z "$CODE_LISTENING_ON" ]]; then
    echo "Error code server did not start successfully"
    # Reading the logfile, to help with debugging
    ls -al $CODE_SERVER_LOGFILE || true
    cat $CODE_SERVER_LOGFILE || true
    print_install_results_and_exit 1 "Code server did not start successfully" "false"
fi

print_install_results_and_wait
