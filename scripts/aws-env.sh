# Source this file from the repository root; it contains no credentials.
if [ -f .env.aws.local ]; then source .env.aws.local; fi
# Clear endpoint overrides inherited from unrelated local AWS emulators.
while IFS= read -r ray_endpoint_variable; do
  if [ -n "$ray_endpoint_variable" ]; then unset "$ray_endpoint_variable"; fi
done < <(python3 -c 'import os; print("\n".join(k for k in os.environ if k.startswith("AWS_") and "ENDPOINT" in k))')
unset ray_endpoint_variable
export AWS_PROFILE="${AWS_PROFILE:-ray-assignment-role}"
export AWS_REGION="${AWS_REGION:-ap-southeast-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
export AWS_SDK_LOAD_CONFIG=1
export AWS_IGNORE_CONFIGURED_ENDPOINT_URLS=true
export AWS_EC2_METADATA_DISABLED=true
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_SECURITY_TOKEN
export EXPECTED_AWS_ACCOUNT_ID="${EXPECTED_AWS_ACCOUNT_ID:?Set the expected account in .env.aws.local}"
export PATH="$PWD/.tools:$PATH"
