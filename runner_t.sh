#!/bin/sh

pid=`cat listener.pid`

if [ -z $1 ]; then
    if [ -z $pid ]; then
        python listener.py -r 2>> listener_stderr.log &
        echo $! > listener.pid
        echo 'Started listener'
    else
        echo 'Listener already running'
    fi
else
    if [ -z $pid ]; then
        echo 'Listener not running'
    else
        kill -9 $pid
        echo '' > listener.pid
        echo 'Killed listener'
    fi
fi
