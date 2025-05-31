#!/bin/bash
# Script to run server tests, assuming it's run from the 'server' directory

echo "==========================="
echo "  Running Server Tests     "
echo "==========================="
python -m unittest tests.test_server
RESULT=$?
if [ $RESULT -eq 0 ]; then
  echo "Server tests PASSED"
else
  echo "Server tests FAILED"
fi
exit $RESULT
