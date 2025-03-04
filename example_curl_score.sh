curl -X POST 'http://localhost:8081/api/report' \
  -H "Authorization: Bearer 55a34ae4d98bfa1ca4b29a9f8e3ab34b" \
  -H "Content-Type: application/x-yaml" \
  --data-binary @- << EOF
settings:
  unique_course_name: test-1
task: task_0_0
user_id: seliverstow
score: 90
check_deadline: true
EOF