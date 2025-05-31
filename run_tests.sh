#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "==========================="
echo "  Running Agent Tests      "
echo "==========================="
python -m unittest tests.test_agent
AGENT_TEST_RESULT=$? # Capture exit code

echo ""
echo "==========================="
echo "  Running Server Tests     "
echo "==========================="
python -m unittest tests.test_server
SERVER_TEST_RESULT=$? # Capture exit code

echo ""
echo "==========================="
echo "  All Tests Complete       "
echo "==========================="

# Check results and exit with appropriate code
if [ $AGENT_TEST_RESULT -ne 0 ] || [ $SERVER_TEST_RESULT -ne 0 ]; then
    echo "One or more test suites failed."
    exit 1
else
    echo "All test suites passed successfully."
    exit 0
fi
