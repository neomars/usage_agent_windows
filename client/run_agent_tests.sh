#!/bin/bash
# Script to run agent tests, assuming it's run from the 'client' directory

echo "==========================="
echo "  Running Agent Tests      "
echo "==========================="
python -m unittest tests.test_agent
RESULT=$?
if [ $RESULT -eq 0 ]; then
  echo "Agent tests PASSED"
else
  echo "Agent tests FAILED"
fi
exit $RESULT
