$ErrorActionPreference = "Stop"

$base   = "http://localhost:8000"
$apiKey = "hr-dev-key"
$headers = @{ "X-API-Key" = $apiKey }

Write-Host "[1/8] healthz 확인" -ForegroundColor Cyan
Invoke-RestMethod "$base/healthz" | Out-Null

Write-Host "[2/8] 필수 라우트 확인" -ForegroundColor Cyan
$paths = (Invoke-RestMethod "$base/openapi.json").paths.PSObject.Properties.Name
$need = @("/v1/candidates", "/v1/resumes/upload", "/v1/resumes/{resume_id}/parse", "/v1/questions/generate")
$missing = $need | Where-Object { $_ -notin $paths }
if ($missing.Count -gt 0) {
  Write-Host "필수 라우트 누락: $($missing -join ', ')" -ForegroundColor Red
  exit 1
}

Write-Host "[3/8] 샘플 이력서 파일 생성" -ForegroundColor Cyan
@"
Kim Minsu
Backend Engineer
- Built API services with FastAPI
- Improved response latency by 30%
- Led incident response and root-cause analysis
"@ | Set-Content -Encoding UTF8 .\sample_resume.txt

Write-Host "[4/8] 후보자 생성" -ForegroundColor Cyan
$candidate = Invoke-RestMethod -Method POST -Uri "$base/v1/candidates" -Headers $headers -ContentType "application/json" -Body (@{
  full_name   = "Kim Minsu"
  email       = "minsu@example.com"
  target_role = "Backend Engineer"
} | ConvertTo-Json)
$candidateId = $candidate.candidate_id
Write-Host "candidate_id=$candidateId" -ForegroundColor Yellow

Write-Host "[5/8] 이력서 업로드 (PS5 호환: curl.exe)" -ForegroundColor Cyan
$uploadRaw = curl.exe -s -X POST `
  -H "X-API-Key: $apiKey" `
  -F "candidate_id=$candidateId" `
  -F "file=@sample_resume.txt;type=text/plain" `
  "$base/v1/resumes/upload"
$upload = $uploadRaw | ConvertFrom-Json
$resumeId = $upload.resume_id
if (-not $resumeId) { throw "resume_id 생성 실패. uploadRaw=$uploadRaw" }
Write-Host "resume_id=$resumeId" -ForegroundColor Yellow

Write-Host "[6/8] 파싱" -ForegroundColor Cyan
$parsed = Invoke-RestMethod -Method POST -Uri "$base/v1/resumes/$resumeId/parse" -Headers $headers

Write-Host "[7/8] 질문 생성" -ForegroundColor Cyan
$qset = Invoke-RestMethod -Method POST -Uri "$base/v1/questions/generate" -Headers $headers -ContentType "application/json" -Body (@{
  candidate_id = $candidateId
  resume_id    = $resumeId
} | ConvertTo-Json)

Write-Host "[8/8] 결과 저장" -ForegroundColor Cyan
$qset | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 .\question_set.json

$lines = @()
$lines += "Question Set ID: $($qset.question_set_id)"
$lines += "Candidate ID: $($qset.candidate_id)"
$lines += "Resume ID: $($qset.resume_id)"
$lines += ""
$i = 1
foreach($q in $qset.questions){
  $lines += "[$i] [$($q.type)] $($q.question)"
  $lines += " - intent: $($q.intent)"
  $lines += " - difficulty: $($q.difficulty)"
  $lines += " - evidence: $($q.evidence)"
  $lines += ""
  $i++
}
$lines | Set-Content -Encoding UTF8 .\interviewer_packet.txt

Write-Host "완료: question_set.json, interviewer_packet.txt 생성됨" -ForegroundColor Green
