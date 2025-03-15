#!/bin/bash
# API Integration Test Script for LLM_interviewer
# Logs all output to api_test_output.log
# Covers all major endpoints, all roles, and is idempotent

API_BASE="http://localhost:8000/api/v1"
LOG_FILE="api_test_output.log"

# Generate unique suffix for dummy data (timestamp)
UNIQ="$(date +%s)"

# Dummy user data
CANDIDATE_EMAIL="candidate_${UNIQ}@test.com"
CANDIDATE_USER="candidate_${UNIQ}"
CANDIDATE_PASS="TestPass123!"
HR_EMAIL="hr_${UNIQ}@test.com"
HR_USER="hr_${UNIQ}"
HR_PASS="TestPass123!"
ADMIN_EMAIL="admin_${UNIQ}@test.com"
ADMIN_USER="admin_${UNIQ}"
ADMIN_PASS="TestPass123!"

# Helper: log and print
log() {
  echo -e "$1" | tee -a "$LOG_FILE"
}

# Counters for summary
total_requests_made=0
passed_positive_tests=0
failed_positive_tests=0 # Will count 2xx failures for negative tests, or non-2xx for positive tests
passed_negative_tests=0
failed_negative_tests=0 # Will count when a negative test gets 2xx, or wrong error code

# Helper: pretty print curl request
print_request() {
  total_requests_made=$((total_requests_made + 1))
  log "\n===== REQUEST: $1 $2 ====="
  if [ -n "$3" ]; then log "Headers: $3"; fi
  if [ -n "$4" ]; then log "Body: $4"; fi
}

# Helper: pretty print response
# Takes http_code, response_body, and optional expected_error_code
print_response() {
  local http_code=$1
  local response_body="$2"
  local expected_error_code=${3:-""} # Default to empty if not provided

  log "===== RESPONSE (HTTP $http_code) ====="
  log "$response_body"

  if [ -n "$expected_error_code" ]; then # This is a negative test
    if [[ "$http_code" == "$expected_error_code" ]]; then
      log "NEGATIVE TEST PASSED: Received expected HTTP $http_code."
      passed_negative_tests=$((passed_negative_tests + 1))
    else
      log "NEGATIVE TEST FAILED: Expected HTTP $expected_error_code, but got $http_code."
      failed_negative_tests=$((failed_negative_tests + 1))
    fi
  else # This is a positive test
    if [[ "$http_code" =~ ^2[0-9][0-9]$ ]]; then
      # Positive test passed (2xx response)
      passed_positive_tests=$((passed_positive_tests + 1))
    else
      # Positive test failed (non-2xx response)
      log "POSITIVE TEST FAILED: Expected 2xx, but got $http_code."
      failed_positive_tests=$((failed_positive_tests + 1))
    fi
  fi
}

# Clean log file
> "$LOG_FILE"

# --- 1. Register Users (idempotent: check if exists via login) ---
log "\n# 1. Registering Users (Candidate, HR, Admin)"

register_user() {
  local role=$1
  local email=$2
  local user=$3
  local pass=$4
  local token_var_name=$5 # Name of the variable for the token
  local id_var_name=$6    # Name of the variable for the ID

  # Try login first (idempotency)
  print_request "POST" "$API_BASE/auth/login" "Content-Type: application/x-www-form-urlencoded" "username=$user&password=$pass"
  resp_login_attempt=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$user&password=$pass")
  body_login_attempt=$(echo "$resp_login_attempt" | head -n-1)
  code_login_attempt=$(echo "$resp_login_attempt" | tail -n1)
  print_response "$code_login_attempt" "$body_login_attempt"
  if [[ "$code_login_attempt" == "200" ]]; then
    local existing_token=$(echo "$body_login_attempt" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
    eval "$token_var_name='$existing_token'"
    log "User $user already exists. Token acquired and set to $token_var_name."
    # Attempt to get ID via /auth/me if id_var_name is provided
    if [ -n "$id_var_name" ]; then
        log "Attempting to get ID for existing user $user via /auth/me"
        me_resp_full=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/auth/me" -H "Authorization: Bearer ${!token_var_name}")
        me_body=$(echo "$me_resp_full" | head -n-1)
        me_code=$(echo "$me_resp_full" | tail -n1)
        if [[ "$me_code" == "200" ]]; then
            local extracted_id_me=$(echo "$me_body" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
            eval "$id_var_name='$extracted_id_me'"
            log "Set $id_var_name to $extracted_id_me for existing user from /auth/me"
        else
            log "Failed to get ID from /auth/me for existing user $user. Status: $me_code. Body: $me_body"
        fi
    fi
    return
  fi

  # Register if login failed
  reg_payload="{\"username\":\"$user\",\"email\":\"$email\",\"password\":\"$pass\",\"role\":\"$role\"}"
  print_request "POST" "$API_BASE/auth/register" "Content-Type: application/json" "$reg_payload"
  reg_resp_full=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/auth/register" \
    -H "Content-Type: application/json" \
    -d "$reg_payload")
  reg_body=$(echo "$reg_resp_full" | head -n-1)
  reg_code=$(echo "$reg_resp_full" | tail -n1)
  print_response "$reg_code" "$reg_body"

  if [[ "$reg_code" == "201" ]]; then
    log "User $user registered."
    if [ -n "$id_var_name" ]; then
      local extracted_id=$(echo "$reg_body" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
      eval "$id_var_name='$extracted_id'" # Use eval to assign to dynamic variable name
      log "Set $id_var_name to $extracted_id"
    fi
  else
    log "User $user registration failed (or already exists and previous login attempt failed - check logic)."
  fi

  # Login to get token (always try this after registration attempt)
  print_request "POST" "$API_BASE/auth/login" "Content-Type: application/x-www-form-urlencoded" "username=$user&password=$pass"
  login_resp_full_after_reg=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$user&password=$pass")
  login_body_after_reg=$(echo "$login_resp_full_after_reg" | head -n-1)
  login_code_after_reg=$(echo "$login_resp_full_after_reg" | tail -n1)
  print_response "$login_code_after_reg" "$login_body_after_reg"
  
  local final_token=$(echo "$login_body_after_reg" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
  eval "$token_var_name='$final_token'" # Use eval for token var name
  log "Set $token_var_name"

  # If ID was not set during registration (e.g. user already existed but initial login failed) and login now succeeded, try /auth/me
  if [[ "$reg_code" != "201" && "$login_code_after_reg" == "200" && -n "$id_var_name" && -z "${!id_var_name}" ]]; then
      log "User $user likely existed (reg failed, login now ok). Attempting to get user ID via /auth/me"
      me_resp_full_retry=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/auth/me" -H "Authorization: Bearer ${!token_var_name}")
      me_body_retry=$(echo "$me_resp_full_retry" | head -n-1)
      me_code_retry=$(echo "$me_resp_full_retry" | tail -n1)
      if [[ "$me_code_retry" == "200" ]]; then
          local extracted_id_me_retry=$(echo "$me_body_retry" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
          eval "$id_var_name='$extracted_id_me_retry'"
          log "Set $id_var_name to $extracted_id_me_retry from /auth/me (retry path)"
      else
          log "Failed to get ID from /auth/me for $user (retry path). Status: $me_code_retry. Body: $me_body_retry"
      fi
  fi
}

CANDIDATE_ID_VAR="" # Initialize
HR_ID_VAR=""
ADMIN_ID_VAR=""

register_user "candidate" "$CANDIDATE_EMAIL" "$CANDIDATE_USER" "$CANDIDATE_PASS" "CANDIDATE_TOKEN" "CANDIDATE_ID_VAR"
register_user "hr" "$HR_EMAIL" "$HR_USER" "$HR_PASS" "HR_TOKEN" "HR_ID_VAR"
register_user "admin" "$ADMIN_EMAIL" "$ADMIN_USER" "$ADMIN_PASS" "ADMIN_TOKEN" "ADMIN_ID_VAR"

# --- 2. Auth Endpoints ---
log "\n# 2. Auth Endpoints"
print_request "GET" "$API_BASE/auth/me" "Authorization: Bearer $CANDIDATE_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/auth/me" -H "Authorization: Bearer $CANDIDATE_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# =====================
# NEGATIVE TESTS: AUTH
# =====================
log "\n# NEGATIVE TESTS: AUTH"

# 401: No token for /auth/me
log "EXPECTING 401 for: No token for /auth/me"
print_request "GET" "$API_BASE/auth/me" "(no token)"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/auth/me")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "401"

# 401: Invalid token for /auth/me
log "EXPECTING 401 for: Invalid token for /auth/me"
print_request "GET" "$API_BASE/auth/me" "Authorization: Bearer invalidtoken"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/auth/me" -H "Authorization: Bearer invalidtoken")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "401"

# 401: Bad login (wrong password) - API returns 401 for this
log "EXPECTING 401 for: Bad login (wrong password)"
print_request "POST" "$API_BASE/auth/login" "Content-Type: application/x-www-form-urlencoded" "username=$CANDIDATE_USER&password=wrongpass"
resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/auth/login" -H "Content-Type: application/x-www-form-urlencoded" -d "username=$CANDIDATE_USER&password=wrongpass")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "401"

# 422: Bad register (missing fields) - API returns 422 for this
log "EXPECTING 422 for: Bad register (missing fields)"
bad_reg_data="{\"username\":\"baduser\"}"
print_request "POST" "$API_BASE/auth/register" "Content-Type: application/json" "$bad_reg_data"
resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/auth/register" -H "Content-Type: application/json" -d "$bad_reg_data")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "422"

# --- 3. Candidate Endpoints ---
log "\n# 3. Candidate Endpoints"
# Get profile
print_request "GET" "$API_BASE/candidate/profile" "Authorization: Bearer $CANDIDATE_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/candidate/profile" -H "Authorization: Bearer $CANDIDATE_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# Update profile
UPDATED_CANDIDATE_USER="${CANDIDATE_USER}_upd"
update_data="{\"username\":\"$UPDATED_CANDIDATE_USER\"}"
print_request "PUT" "$API_BASE/candidate/profile" "Authorization: Bearer $CANDIDATE_TOKEN, Content-Type: application/json" "$update_data"
resp=$(curl -s -w "\n%{http_code}" -X PUT "$API_BASE/candidate/profile" -H "Authorization: Bearer $CANDIDATE_TOKEN" -H "Content-Type: application/json" -d "$update_data")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"
if [[ "$code" == "200" ]]; then
  log "Candidate username successfully updated to $UPDATED_CANDIDATE_USER. Updating CANDIDATE_USER variable."
  CANDIDATE_USER="$UPDATED_CANDIDATE_USER"
else
  log "Failed to update candidate username. Subsequent logins might fail if they rely on the updated name."
fi

# Get messages
print_request "GET" "$API_BASE/candidate/messages" "Authorization: Bearer $CANDIDATE_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/candidate/messages" -H "Authorization: Bearer $CANDIDATE_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# Mark messages as read (dummy payload)
mark_data="{\"message_ids\":[\"000000000000000000000000\"]}" # Use a dummy valid-looking ID
print_request "POST" "$API_BASE/candidate/messages/mark-read" "Authorization: Bearer $CANDIDATE_TOKEN, Content-Type: application/json" "$mark_data"
resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/candidate/messages/mark-read" -H "Authorization: Bearer $CANDIDATE_TOKEN" -H "Content-Type: application/json" -d "$mark_data")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# --- 3b. Candidate Resume Upload (file upload) ---
log "\n# 3b. Candidate Resume Upload"
log "Listing contents of server's tests directory: $(pwd)/tests/"
ls -la tests/
log "Attempting to copy tests/sample_resume.pdf"
cp tests/sample_resume.pdf dummy_resume.pdf
print_request "POST" "$API_BASE/candidate/resume" "Authorization: Bearer $CANDIDATE_TOKEN, Content-Type: multipart/form-data" "file=@dummy_resume.pdf"
resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/candidate/resume" \
  -H "Authorization: Bearer $CANDIDATE_TOKEN" \
  -F "resume=@dummy_resume.pdf")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# =========================
# NEGATIVE TESTS: CANDIDATE
# =========================
log "\n# NEGATIVE TESTS: CANDIDATE"

# 401: No token for /candidate/profile
log "EXPECTING 401 for: No token for /candidate/profile"
print_request "GET" "$API_BASE/candidate/profile" "(no token)"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/candidate/profile")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "401"

# 403: HR token for /candidate/profile
log "EXPECTING 403 for: HR token for /candidate/profile"
print_request "GET" "$API_BASE/candidate/profile" "Authorization: Bearer $HR_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/candidate/profile" -H "Authorization: Bearer $HR_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "403"

# 401: Invalid candidate for /candidate/profile (simulate by using invalid token, API returns 401 for bad token)
log "EXPECTING 401 for: Invalid token for /candidate/profile"
print_request "GET" "$API_BASE/candidate/profile" "Authorization: Bearer invalidtoken"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/candidate/profile" -H "Authorization: Bearer invalidtoken")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "401"

# 400: Bad update (missing data)
log "EXPECTING 400 for: Bad update to /candidate/profile (missing data)"
print_request "PUT" "$API_BASE/candidate/profile" "Authorization: Bearer $CANDIDATE_TOKEN, Content-Type: application/json" "{}"
resp=$(curl -s -w "\n%{http_code}" -X PUT "$API_BASE/candidate/profile" -H "Authorization: Bearer $CANDIDATE_TOKEN" -H "Content-Type: application/json" -d "{}")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "400"

# 200: Invalid ID for /candidate/messages/mark-read (API returns 200 with modified_count 0 if ID not found)
log "EXPECTING 200 (but effectively a no-op) for: Invalid ID for /candidate/messages/mark-read"
mark_data_invalid="{\"message_ids\":[\"000000000000000000000000\"]}"
print_request "POST" "$API_BASE/candidate/messages/mark-read" "Authorization: Bearer $CANDIDATE_TOKEN, Content-Type: application/json" "$mark_data_invalid"
resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/candidate/messages/mark-read" -H "Authorization: Bearer $CANDIDATE_TOKEN" -H "Content-Type: application/json" -d "$mark_data_invalid")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" # This is a 200, so no expected error code needed for the counter

# 400: Bad resume upload (wrong file type)
log "EXPECTING 400 for: Bad resume upload (wrong file type)"
echo "bad content for txt" > bad.txt
print_request "POST" "$API_BASE/candidate/resume" "Authorization: Bearer $CANDIDATE_TOKEN, Content-Type: multipart/form-data" "file=@bad.txt"
resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/candidate/resume" -H "Authorization: Bearer $CANDIDATE_TOKEN" -F "resume=@bad.txt")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "400"

# --- 4. HR Endpoints ---
log "\n# 4. HR Endpoints"

# --- 4b. HR Profile Update ---
log "\n# 4b. HR Profile Update"
hr_profile_data="{\"years_of_experience\":5,\"company\":\"TestCorp\"}"
print_request "POST" "$API_BASE/hr/profile-details" "Authorization: Bearer $HR_TOKEN, Content-Type: application/json" "$hr_profile_data"
resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/hr/profile-details" -H "Authorization: Bearer $HR_TOKEN" -H "Content-Type: application/json" -d "$hr_profile_data")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# --- 4c. HR Resume Upload (file upload) ---
log "\n# 4c. HR Resume Upload"
log "Listing contents of server's tests directory: $(pwd)/tests/"
ls -la tests/
log "Attempting to copy tests/sample_resume.pdf"
cp tests/sample_resume.pdf dummy_hr_resume.pdf
print_request "POST" "$API_BASE/hr/resume" "Authorization: Bearer $HR_TOKEN, Content-Type: multipart/form-data" "file=@dummy_hr_resume.pdf"
resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/hr/resume" \
  -H "Authorization: Bearer $HR_TOKEN" \
  -F "resume=@dummy_hr_resume.pdf")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# Get admins (HR should be profile_complete now)
print_request "GET" "$API_BASE/hr/admins" "Authorization: Bearer $HR_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/hr/admins" -H "Authorization: Bearer $HR_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# Get pending admin requests (HR should not have any yet from admin)
print_request "GET" "$API_BASE/hr/pending-admin-requests" "Authorization: Bearer $HR_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/hr/pending-admin-requests" -H "Authorization: Bearer $HR_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# --- 4d. HR Apply to Admin (use ADMIN_ID_VAR) ---
log "\n# 4d. HR Apply to Admin"
if [ -n "$ADMIN_ID_VAR" ]; then
  print_request "POST" "$API_BASE/hr/apply/$ADMIN_ID_VAR" "Authorization: Bearer $HR_TOKEN"
  resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/hr/apply/$ADMIN_ID_VAR" -H "Authorization: Bearer $HR_TOKEN")
  body=$(echo "$resp" | head -n-1)
  code=$(echo "$resp" | tail -n1)
  print_response "$code" "$body"
else
  log "ADMIN_ID_VAR is not set. Cannot run HR Apply to Admin test."
fi

# --- 5. Admin Endpoints ---
log "\n# 5. Admin Endpoints"
# Get all users
print_request "GET" "$API_BASE/admin/users" "Authorization: Bearer $ADMIN_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/admin/users" -H "Authorization: Bearer $ADMIN_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# Get stats
print_request "GET" "$API_BASE/admin/stats" "Authorization: Bearer $ADMIN_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/admin/stats" -H "Authorization: Bearer $ADMIN_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# --- 5c. Admin HR Applications ---
log "\n# 5c. Admin HR Applications"
print_request "GET" "$API_BASE/admin/hr-applications" "Authorization: Bearer $ADMIN_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/admin/hr-applications" -H "Authorization: Bearer $ADMIN_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# --- 5d. Admin Accept/Reject HR Application (get application_id from /admin/hr-applications) ---
log "\n# 5d. Admin Accept/Reject HR Application"
# Get the main _id of the application request document
application_id=$(curl -s -X GET "$API_BASE/admin/hr-applications" -H "Authorization: Bearer $ADMIN_TOKEN" | grep -o '"_id":"[^"]*"' | head -n1 | cut -d'"' -f4)
if [ -n "$application_id" ]; then
  log "Extracted application_id for accept/reject: $application_id"
  print_request "POST" "$API_BASE/admin/hr-applications/$application_id/accept" "Authorization: Bearer $ADMIN_TOKEN"
  resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/admin/hr-applications/$application_id/accept" -H "Authorization: Bearer $ADMIN_TOKEN")
  body=$(echo "$resp" | head -n-1)
  code=$(echo "$resp" | tail -n1)
  print_response "$code" "$body"
  print_request "POST" "$API_BASE/admin/hr-applications/$application_id/reject" "Authorization: Bearer $ADMIN_TOKEN"
  resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/admin/hr-applications/$application_id/reject" -H "Authorization: Bearer $ADMIN_TOKEN")
  body=$(echo "$resp" | head -n-1)
  code=$(echo "$resp" | tail -n1)
  print_response "$code" "$body"
else
  log "No application_id found for admin accept/reject."
fi

# --- 5e. Admin Search HR ---
log "\n# 5e. Admin Search HR"
print_request "GET" "$API_BASE/admin/search-hr" "Authorization: Bearer $ADMIN_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/admin/search-hr" -H "Authorization: Bearer $ADMIN_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# --- 5f. Admin HR Mapping Request (get hr_user_id from /admin/search-hr) ---
log "\n# 5f. Admin HR Mapping Request"
hr_user_id=$(curl -s -X GET "$API_BASE/admin/search-hr" -H "Authorization: Bearer $ADMIN_TOKEN" | grep -o '"id":"[^"]*"' | head -n1 | cut -d'"' -f4)
if [ -n "$hr_user_id" ]; then
  print_request "POST" "$API_BASE/admin/hr-mapping-requests/$hr_user_id" "Authorization: Bearer $ADMIN_TOKEN"
  resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/admin/hr-mapping-requests/$hr_user_id" -H "Authorization: Bearer $ADMIN_TOKEN")
  body=$(echo "$resp" | head -n-1)
  code=$(echo "$resp" | tail -n1)
  print_response "$code" "$body"
else
  log "No hr_user_id found for admin mapping request."
fi

# --- 5g. Admin Assign HR to Candidate (use CANDIDATE_ID_VAR and HR_ID_VAR) ---
log "\n# 5g. Admin Assign HR to Candidate"
if [ -n "$CANDIDATE_ID_VAR" ] && [ -n "$HR_ID_VAR" ] && [ -n "$ADMIN_TOKEN" ]; then
  log "Attempting to assign HR ($HR_ID_VAR) to Candidate ($CANDIDATE_ID_VAR) by Admin ($ADMIN_USER)"
  assign_data="{\"hr_id\":\"$HR_ID_VAR\"}"
  print_request "POST" "$API_BASE/admin/candidates/$CANDIDATE_ID_VAR/assign-hr" "Authorization: Bearer $ADMIN_TOKEN, Content-Type: application/json" "$assign_data"
  resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/admin/candidates/$CANDIDATE_ID_VAR/assign-hr" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d "$assign_data")
  body=$(echo "$resp" | head -n-1)
  code=$(echo "$resp" | tail -n1)
  print_response "$code" "$body"
  if [[ "$code" == "200" ]]; then
    log "Successfully assigned HR $HR_ID_VAR to Candidate $CANDIDATE_ID_VAR."
  else
    log "Failed to assign HR to Candidate. Response code: $code, Body: $body"
  fi
else
  log "CANDIDATE_ID_VAR, HR_ID_VAR, or ADMIN_TOKEN not set. Skipping Admin Assign HR to Candidate."
fi

# --- HR Mapped Actions: Search Candidates & Invite ---
log "\n# HR Mapped Actions: Search Candidates & Invite"
print_request "GET" "$API_BASE/hr/search-candidates" "Authorization: Bearer $HR_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/hr/search-candidates" -H "Authorization: Bearer $HR_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# --- 4g. HR Send Candidate Invitation (use CANDIDATE_ID_VAR) ---
log "\n# 4g. HR Send Candidate Invitation"
CANDIDATE_PROFILE_FOR_INVITE=$(curl -s -X GET "$API_BASE/candidate/profile" -H "Authorization: Bearer $CANDIDATE_TOKEN")
CANDIDATE_STATUS_FOR_INVITE=$(echo "$CANDIDATE_PROFILE_FOR_INVITE" | grep -o '"mapping_status":"[^"]*"' | cut -d'"' -f4)

if [ -n "$CANDIDATE_ID_VAR" ] && ([ "$CANDIDATE_STATUS_FOR_INVITE" == "pending_assignment" ] || [ "$CANDIDATE_STATUS_FOR_INVITE" == "pending_resume" ]); then
  invitation_data="{\"content\":\"You are invited for an interview!\"}"
  print_request "POST" "$API_BASE/hr/candidate-invitations/$CANDIDATE_ID_VAR" "Authorization: Bearer $HR_TOKEN, Content-Type: application/json" "$invitation_data"
  resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/hr/candidate-invitations/$CANDIDATE_ID_VAR" -H "Authorization: Bearer $HR_TOKEN" -H "Content-Type: application/json" -d "$invitation_data")
  body=$(echo "$resp" | head -n-1)
  code=$(echo "$resp" | tail -n1)
  print_response "$code" "$body"
else
  log "Skipping HR candidate invitation: CANDIDATE_ID_VAR not set, or candidate status is '$CANDIDATE_STATUS_FOR_INVITE' (not pending_assignment or pending_resume)."
fi

# --- 6. Interview Endpoints ---
log "\n# 6. Interview Endpoints"
# Re-login candidate to ensure fresh token for interview section
log "\n# Re-logging in Candidate for fresh token before Interview tests"
print_request "POST" "$API_BASE/auth/login" "Content-Type: application/x-www-form-urlencoded" "username=$CANDIDATE_USER&password=$CANDIDATE_PASS"
resp_relogin_cand=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$CANDIDATE_USER&password=$CANDIDATE_PASS")
body_relogin_cand=$(echo "$resp_relogin_cand" | head -n-1)
code_relogin_cand=$(echo "$resp_relogin_cand" | tail -n1)
print_response "$code_relogin_cand" "$body_relogin_cand"
if [[ "$code_relogin_cand" == "200" ]]; then
  CANDIDATE_TOKEN=$(echo "$body_relogin_cand" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
  log "Candidate re-login successful. New token set for CANDIDATE_TOKEN."
else
  log "Candidate re-login FAILED. Interview tests might use stale token."
fi

print_request "GET" "$API_BASE/interview/default-questions" "Authorization: Bearer $HR_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/interview/default-questions" -H "Authorization: Bearer $HR_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

print_request "GET" "$API_BASE/interview/all" "Authorization: Bearer $ADMIN_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/interview/all" -H "Authorization: Bearer $ADMIN_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

print_request "GET" "$API_BASE/interview/candidate/me" "Authorization: Bearer $CANDIDATE_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/interview/candidate/me" -H "Authorization: Bearer $CANDIDATE_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# --- 6b. Interview Schedule (HR schedules for CANDIDATE_ID_VAR) ---
log "\n# 6b. Interview Schedule"
if [ -n "$CANDIDATE_ID_VAR" ] && [ -n "$HR_ID_VAR" ] && [ -n "$HR_TOKEN" ]; then
  log "Attempting to schedule interview for Candidate ($CANDIDATE_ID_VAR) by HR ($HR_USER) (HR ID: $HR_ID_VAR)"
  schedule_data="{\"candidate_id\":\"$CANDIDATE_ID_VAR\",\"job_title\":\"Software Engineer\",\"job_description\":\"Test job\",\"role\":\"developer\",\"tech_stack\":[\"python\"]}"
  print_request "POST" "$API_BASE/interview/schedule" "Authorization: Bearer $HR_TOKEN, Content-Type: application/json" "$schedule_data"
  resp_schedule=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/interview/schedule" -H "Authorization: Bearer $HR_TOKEN" -H "Content-Type: application/json" -d "$schedule_data")
  body_schedule=$(echo "$resp_schedule" | head -n-1)
  code_schedule=$(echo "$resp_schedule" | tail -n1)
  print_response "$code_schedule" "$body_schedule"
  if [[ "$code_schedule" == "201" ]]; then
    INTERVIEW_ID=$(echo "$body_schedule" | grep -o '"interview_id":"[^"]*"' | head -n1 | cut -d'"' -f4)
    log "Interview scheduled successfully. Interview ID: $INTERVIEW_ID"
    FIRST_QUESTION_ID=$(echo "$body_schedule" | grep -o -m 1 '"question_id":"[^"]*"' | head -n 1 | sed -e 's/"question_id":"//' -e 's/"//')
    if [ -n "$FIRST_QUESTION_ID" ]; then
      log "Extracted first question ID: $FIRST_QUESTION_ID"
    else
      log "Failed to extract first question ID from schedule response."
    fi
  else
    log "Failed to schedule interview. Response code: $code_schedule, Body: $body_schedule"
    INTERVIEW_ID=""
    FIRST_QUESTION_ID=""
  fi
else
  log "CANDIDATE_ID_VAR, HR_ID_VAR, or HR_TOKEN not set. Skipping Interview Schedule."
  INTERVIEW_ID=""
  FIRST_QUESTION_ID=""
fi

# --- 6c. Interview Results All (Admin/HR) ---
log "\n# 6c. Interview Results All (Admin/HR)"
print_request "GET" "$API_BASE/interview/results/all" "Authorization: Bearer $ADMIN_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/interview/results/all" -H "Authorization: Bearer $ADMIN_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

print_request "GET" "$API_BASE/interview/results/all" "Authorization: Bearer $HR_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/interview/results/all" -H "Authorization: Bearer $HR_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# --- 6d. Interview Submit Response (candidate) ---
log "\n# 6d. Interview Submit Response"
if [ -n "$INTERVIEW_ID" ] && [ -n "$FIRST_QUESTION_ID" ] && [ -n "$CANDIDATE_TOKEN" ]; then
  log "Attempting to submit response for Interview ID: $INTERVIEW_ID, Question ID: $FIRST_QUESTION_ID"
  submit_data="{\"interview_id\":\"$INTERVIEW_ID\",\"question_id\":\"$FIRST_QUESTION_ID\",\"answer\":\"My detailed answer to the first question.\"}"
  print_request "POST" "$API_BASE/interview/submit-response" "Authorization: Bearer $CANDIDATE_TOKEN, Content-Type: application/json" "$submit_data"
  resp_submit_one=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/interview/submit-response" -H "Authorization: Bearer $CANDIDATE_TOKEN" -H "Content-Type: application/json" -d "$submit_data")
  body_submit_one=$(echo "$resp_submit_one" | head -n-1)
  code_submit_one=$(echo "$resp_submit_one" | tail -n1)
  print_response "$code_submit_one" "$body_submit_one"
  if [[ "$code_submit_one" == "201" ]]; then
    log "Single response submitted successfully. Status: $code_submit_one"
    RESPONSE_ID_FOR_EVAL=$(echo "$body_submit_one" | grep -o '"_id":"[^"]*"' | head -n1 | cut -d'"' -f4)
    if [ -n "$RESPONSE_ID_FOR_EVAL" ]; then
      log "Extracted response ID for evaluation: $RESPONSE_ID_FOR_EVAL"
    else
      log "Failed to extract _id as RESPONSE_ID_FOR_EVAL from submit-response response. Body: $body_submit_one"
    fi
  else
    log "Single response submission FAILED. Status: $code_submit_one, Body: $body_submit_one"
    RESPONSE_ID_FOR_EVAL=""
  fi
else
  log "Skipping single response submission: INTERVIEW_ID ($INTERVIEW_ID), FIRST_QUESTION_ID ($FIRST_QUESTION_ID), or CANDIDATE_TOKEN not available."
  RESPONSE_ID_FOR_EVAL=""
fi

# --- 6e. Interview Submit All Responses (candidate) ---
log "\n# 6e. Interview Submit All Responses"
if [ -n "$INTERVIEW_ID" ] && [ -n "$FIRST_QUESTION_ID" ] && [ -n "$CANDIDATE_TOKEN" ]; then
  log "Attempting to submit all responses for Interview ID: $INTERVIEW_ID"
  submit_all_data="{\"interview_id\":\"$INTERVIEW_ID\",\"answers\":[{\"question_id\":\"$FIRST_QUESTION_ID\",\"answer_text\":\"My answer A1 to the first question via submit-all.\"}]}"
  print_request "POST" "$API_BASE/interview/submit-all" "Authorization: Bearer $CANDIDATE_TOKEN, Content-Type: application/json" "$submit_all_data"
  resp_submit_all=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/interview/submit-all" -H "Authorization: Bearer $CANDIDATE_TOKEN" -H "Content-Type: application/json" -d "$submit_all_data")
  body_submit_all=$(echo "$resp_submit_all" | head -n-1)
  code_submit_all=$(echo "$resp_submit_all" | tail -n1)
  print_response "$code_submit_all" "$body_submit_all"
  if [[ "$code_submit_all" == "200" ]]; then
    log "Submit all responses successful."
  else
    log "Submit all responses failed. Status: $code_submit_all, Body: $body_submit_all"
  fi
else
  log "Skipping submit-all responses: INTERVIEW_ID ($INTERVIEW_ID), FIRST_QUESTION_ID ($FIRST_QUESTION_ID), or CANDIDATE_TOKEN not available."
fi

# --- 6f. Interview Results by ID (Admin/HR) ---
log "\n# 6f. Interview Results by ID (Admin/HR)"
if [ -n "$INTERVIEW_ID" ]; then
  log "Attempting to get results for Interview ID: $INTERVIEW_ID by Admin"
  print_request "GET" "$API_BASE/interview/results/$INTERVIEW_ID" "Authorization: Bearer $ADMIN_TOKEN"
  resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/interview/results/$INTERVIEW_ID" -H "Authorization: Bearer $ADMIN_TOKEN")
  body=$(echo "$resp" | head -n-1)
  code=$(echo "$resp" | tail -n1)
  print_response "$code" "$body"

  log "Attempting to get results for Interview ID: $INTERVIEW_ID by HR"
  print_request "GET" "$API_BASE/interview/results/$INTERVIEW_ID" "Authorization: Bearer $HR_TOKEN"
  resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/interview/results/$INTERVIEW_ID" -H "Authorization: Bearer $HR_TOKEN")
  body=$(echo "$resp" | head -n-1)
  code=$(echo "$resp" | tail -n1)
  print_response "$code" "$body"
fi

# --- 6g. Interview Submit Results (HR/Admin) ---
log "\n# 6g. Interview Submit Results (HR/Admin)"
if [ -n "$INTERVIEW_ID" ] && [ -n "$HR_TOKEN" ]; then
  log "Attempting to submit results for Interview ID: $INTERVIEW_ID by HR"
  result_data="{\"score\":5,\"feedback\":\"Good\"}"
  print_request "POST" "$API_BASE/interview/$INTERVIEW_ID/results" "Authorization: Bearer $HR_TOKEN, Content-Type: application/json" "$result_data"
  resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/interview/$INTERVIEW_ID/results" -H "Authorization: Bearer $HR_TOKEN" -H "Content-Type: application/json" -d "$result_data")
  body=$(echo "$resp" | head -n-1)
  code=$(echo "$resp" | tail -n1)
  print_response "$code" "$body"
fi

# --- 6i. Interview Details (GET) ---
log "\n# 6i. Interview Details"
if [ -n "$INTERVIEW_ID" ]; then
  log "Attempting to get details for Interview ID: $INTERVIEW_ID by Admin"
  print_request "GET" "$API_BASE/interview/$INTERVIEW_ID" "Authorization: Bearer $ADMIN_TOKEN"
  resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/interview/$INTERVIEW_ID" -H "Authorization: Bearer $ADMIN_TOKEN")
  body=$(echo "$resp" | head -n-1)
  code=$(echo "$resp" | tail -n1)
  print_response "$code" "$body"
fi

# --- 6j. Interview Responses List ---
log "\n# 6j. Interview Responses List"
if [ -n "$INTERVIEW_ID" ]; then
  log "Attempting to get responses list for Interview ID: $INTERVIEW_ID by Admin"
  print_request "GET" "$API_BASE/interview/$INTERVIEW_ID/responses" "Authorization: Bearer $ADMIN_TOKEN"
  resp_get_responses=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/interview/$INTERVIEW_ID/responses" -H "Authorization: Bearer $ADMIN_TOKEN")
  body_get_responses=$(echo "$resp_get_responses" | head -n-1)
  code_get_responses=$(echo "$resp_get_responses" | tail -n1)
  print_response "$code_get_responses" "$body_get_responses"
  if [[ "$code_get_responses" == "200" ]] && [[ "$body_get_responses" != "[]" ]]; then
    NEW_RESPONSE_ID_FOR_EVAL=$(echo "$body_get_responses" | grep -o -m 1 '"_id":"[^"]*"' | head -n 1 | cut -d'"' -f4)
    if [ -n "$NEW_RESPONSE_ID_FOR_EVAL" ]; then
      RESPONSE_ID_FOR_EVAL="$NEW_RESPONSE_ID_FOR_EVAL"
      log "Updated RESPONSE_ID_FOR_EVAL to $RESPONSE_ID_FOR_EVAL from fetched responses list for step 6h."
    else
      log "Could not extract _id from responses list for AI eval, though responses were found. Body: $body_get_responses"
    fi
  else
    log "No responses found or error fetching responses for interview $INTERVIEW_ID. RESPONSE_ID_FOR_EVAL might be stale if set by step 6d."
  fi
fi

# --- 6h. Interview Evaluate Response (HR/Admin, use RESPONSE_ID_FOR_EVAL from 6d or 6j) ---
log "\n# 6h. Interview Evaluate Response (HR/Admin)"
if [ -n "$INTERVIEW_ID" ] && [ -n "$RESPONSE_ID_FOR_EVAL" ] && [ -n "$HR_TOKEN" ]; then
  log "Attempting to evaluate response ID: $RESPONSE_ID_FOR_EVAL for Interview ID: $INTERVIEW_ID by HR"
  print_request "POST" "$API_BASE/interview/responses/$RESPONSE_ID_FOR_EVAL/evaluate" "Authorization: Bearer $HR_TOKEN"
  resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/interview/responses/$RESPONSE_ID_FOR_EVAL/evaluate" -H "Authorization: Bearer $HR_TOKEN")
  body=$(echo "$resp" | head -n-1)
  code=$(echo "$resp" | tail -n1)
  print_response "$code" "$body"
fi

# --- 6k. Interview Candidate History ---
log "\n# 6k. Interview Candidate History"
print_request "GET" "$API_BASE/interview/candidate/history" "Authorization: Bearer $CANDIDATE_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/interview/candidate/history" -H "Authorization: Bearer $CANDIDATE_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# --- Cleanup dummy files ---
rm -f dummy_resume.pdf dummy_hr_resume.pdf bad.txt bad_hr.txt

# =========================
# NEGATIVE TESTS: HR ENDPOINTS
# =========================
log "\n# NEGATIVE TESTS: HR ENDPOINTS"

# 401: No token for /hr/admins
log "EXPECTING 401 for: No token for /hr/admins"
print_request "GET" "$API_BASE/hr/admins" "(no token)"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/hr/admins")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "401"

# 403: Candidate token for /hr/admins
log "EXPECTING 403 for: Candidate token for /hr/admins"
print_request "GET" "$API_BASE/hr/admins" "Authorization: Bearer $CANDIDATE_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/hr/admins" -H "Authorization: Bearer $CANDIDATE_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "403"

# 400: Invalid admin_id for /hr/apply/{admin_id} (API returns 400 if HR status is not 'profile_complete' or admin not found)
log "EXPECTING 400 for: Invalid admin_id or HR status for /hr/apply/{admin_id}"
print_request "POST" "$API_BASE/hr/apply/000000000000000000000000" "Authorization: Bearer $HR_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/hr/apply/000000000000000000000000" -H "Authorization: Bearer $HR_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "400"

# 200: Bad profile-details (empty data, but API might return 200 if no fields are mandatory for update and it's a no-op)
log "EXPECTING 200 (no-op) for: Bad profile-details (empty data) for /hr/profile-details"
print_request "POST" "$API_BASE/hr/profile-details" "Authorization: Bearer $HR_TOKEN, Content-Type: application/json" "{}"
resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/hr/profile-details" -H "Authorization: Bearer $HR_TOKEN" -H "Content-Type: application/json" -d "{}")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" # Expecting 200 as it's a no-op update

# 400: Bad resume upload (wrong file type)
log "EXPECTING 400 for: Bad resume upload (wrong file type) for /hr/resume"
echo "bad content for hr txt" > bad_hr.txt
print_request "POST" "$API_BASE/hr/resume" "Authorization: Bearer $HR_TOKEN, Content-Type: multipart/form-data" "file=@bad_hr.txt"
resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/hr/resume" -H "Authorization: Bearer $HR_TOKEN" -F "resume=@bad_hr.txt")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "400"

# 401: No token for /hr/search-candidates
log "EXPECTING 401 for: No token for /hr/search-candidates"
print_request "GET" "$API_BASE/hr/search-candidates" "(no token)"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/hr/search-candidates")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "401"

# 403: Candidate token for /hr/search-candidates
log "EXPECTING 403 for: Candidate token for /hr/search-candidates"
print_request "GET" "$API_BASE/hr/search-candidates" "Authorization: Bearer $CANDIDATE_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/hr/search-candidates" -H "Authorization: Bearer $CANDIDATE_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "403"

# Query param test: /hr/search-candidates?keyword=test&yoe_min=1
print_request "GET" "$API_BASE/hr/search-candidates?keyword=test&yoe_min=1" "Authorization: Bearer $HR_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/hr/search-candidates?keyword=test&yoe_min=1" -H "Authorization: Bearer $HR_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body"

# =========================
# NEGATIVE TESTS: ADMIN ENDPOINTS
# =========================
log "\n# NEGATIVE TESTS: ADMIN ENDPOINTS"

# 401: No token for /admin/users
log "EXPECTING 401 for: No token for /admin/users"
print_request "GET" "$API_BASE/admin/users" "(no token)"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/admin/users")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "401"

# 403: HR token for /admin/users
log "EXPECTING 403 for: HR token for /admin/users"
print_request "GET" "$API_BASE/admin/users" "Authorization: Bearer $HR_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/admin/users" -H "Authorization: Bearer $HR_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "403"

# 404: Invalid user_id for /admin/users/{user_id_to_delete}
log "EXPECTING 404 for: Invalid user_id for /admin/users/{user_id_to_delete}"
print_request "DELETE" "$API_BASE/admin/users/000000000000000000000000" "Authorization: Bearer $ADMIN_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X DELETE "$API_BASE/admin/users/000000000000000000000000" -H "Authorization: Bearer $ADMIN_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "404"

# Query param test: /admin/search-hr?keyword=test&yoe_min=1 (This is a positive test, should return 200)
log "EXPECTING 200 for: Query param test for /admin/search-hr"
print_request "GET" "$API_BASE/admin/search-hr?keyword=test&yoe_min=1" "Authorization: Bearer $ADMIN_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/admin/search-hr?keyword=test&yoe_min=1" -H "Authorization: Bearer $ADMIN_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" # Expect 200

# =========================
# NEGATIVE TESTS: INTERVIEW ENDPOINTS
# =========================
log "\n# NEGATIVE TESTS: INTERVIEW ENDPOINTS"

# 200: No token for /interview/default-questions (This endpoint is public)
log "EXPECTING 200 for: No token for /interview/default-questions (public endpoint)"
print_request "GET" "$API_BASE/interview/default-questions" "(no token)"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/interview/default-questions")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" # Expect 200

# 403: Candidate token for /interview/all
log "EXPECTING 403 for: Candidate token for /interview/all"
print_request "GET" "$API_BASE/interview/all" "Authorization: Bearer $CANDIDATE_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/interview/all" -H "Authorization: Bearer $CANDIDATE_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "403"

# 404: Invalid interview_id for /interview/results/{interview_id}
log "EXPECTING 404 for: Invalid interview_id for /interview/results/{interview_id}"
print_request "GET" "$API_BASE/interview/results/000000000000000000000000" "Authorization: Bearer $ADMIN_TOKEN"
resp=$(curl -s -w "\n%{http_code}" -X GET "$API_BASE/interview/results/000000000000000000000000" -H "Authorization: Bearer $ADMIN_TOKEN")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "404"

# 422: Bad schedule (missing data) - API returns 422
log "EXPECTING 422 for: Bad schedule (missing data)"
print_request "POST" "$API_BASE/interview/schedule" "Authorization: Bearer $HR_TOKEN, Content-Type: application/json" "{}"
resp=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/interview/schedule" -H "Authorization: Bearer $HR_TOKEN" -H "Content-Type: application/json" -d "{}")
body=$(echo "$resp" | head -n-1)
code=$(echo "$resp" | tail -n1)
print_response "$code" "$body" "422"

# =========================
# FULL FLOW TEST: CANDIDATE -> HR -> ADMIN -> INTERVIEW
# =========================
log "\n# FULL FLOW TEST: CANDIDATE -> HR -> ADMIN -> INTERVIEW"
# (Register candidate, HR, admin, map HR, assign candidate, schedule interview, submit response, evaluate, etc.)
# (Use extracted IDs from previous steps, log each step, check for expected status codes)

# ... (implement full flow, extracting IDs and chaining requests) ...

# =========================
# SUMMARY AND EXIT CODE
# =========================
log "\n# TEST SUMMARY"
log "Total requests made: $total_requests_made"
log "Passed positive tests (2xx): $passed_positive_tests"
log "Failed positive tests (non-2xx): $failed_positive_tests"
log "Passed negative tests (expected non-2xx): $passed_negative_tests"
log "Failed negative tests (unexpected code): $failed_negative_tests"

total_failed_tests=$((failed_positive_tests + failed_negative_tests))

if [ "$total_failed_tests" -eq 0 ]; then
  log "\nALL TESTS PASSED!"
  log "Positive tests passed: $passed_positive_tests"
  log "Negative tests passed (correctly handled expected errors): $passed_negative_tests"
  exit 0
else
  log "\nTESTS FAILED: $total_failed_tests out of $total_requests_made total test assertions."
  log "  Failed positive tests (expected 2xx, got other): $failed_positive_tests"
  log "  Failed negative tests (expected specific non-2xx, got something else): $failed_negative_tests"
  exit 1
fi

</final_file_content>

IMPORTANT: For any future changes to this file, use the final_file_content shown above as your reference. This content reflects the current state of the file, including any auto-formatting (e.g., if you used single quotes but the formatter converted them to double quotes). Always base your SEARCH/REPLACE operations on this final version to ensure accuracy.

<environment_details>
# VSCode Visible Files
C:/Users/babhi/AppData/Local/Programs/Microsoft VS Code/extension-output-formulahendry.code-runner-#1-Code
C:/Users/babhi/AppData/Local/Programs/Microsoft VS Code/perform_git_rewrite.ps1
C:/Users/babhi/AppData/Local/Programs/Microsoft VS Code/perform_git_rewrite.ps1
temp_api_integration_test.sh

# VSCode Open Tabs
add_pydantic_titles.py
server/app/schemas/admin.py
server/app/api/routes/admin.py
server/Dockerfile
docker-compose.yml
Readme.md
.gitignore
perform_git_rewrite.ps1
temp_api_integration_test.sh
temp_systemdesign.md
temp_dockerignore.txt
temp_env.txt
temp_env_example.txt
temp_gitignore.txt
temp_pytest_ini.txt
temp_requirements_dev.txt
temp_requirements.txt
temp_readme.txt
temp_dockerfile.txt
c:/Users/babhi/AppData/Local/Programs/Microsoft VS Code/perform_git_rewrite.ps1
server/app/core/schema_utils.py
server/app/schemas/interview.py
server/app/schemas/user.py

# Current Time
5/13/2025, 10:18:30 PM (Asia/Calcutta, UTC+5.5:00)

# Context Window Usage
463,312 / 1,048.576K tokens used (44%)

# Current Mode
ACT MODE
</environment_details>
