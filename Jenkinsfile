// Jenkinsfile for German AI Tutor Monorepo - Host-based Push Check Pipeline
pipeline {
    agent any

    environment {
        GEMINI_API_KEY = credentials('GEMINI_API_KEY_SECRET')
    }

    options {
        timeout(time: 15, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    triggers {
        pollSCM('* * * * *')
    }

    stages {
        stage('Guard') {
            steps {
                script {
                    def currentBranch = env.GIT_BRANCH ?: ''
                    echo "Processing branch: ${currentBranch}"
                    if (currentBranch.endsWith('/main') || currentBranch == 'main') {
                        error("Aborting build: This pipeline should not run on the 'main' branch.")
                    }
                }
            }
        }

        stage('Parallel Checks') {
            steps {
                // Початок GitHub Check (IN_PROGRESS)
                githubChecks(
                    name: 'CI / Push Checks',
                    status: 'IN_PROGRESS',
                    account: 'vitwits',
                    repo: 'language-AI-tutor',
                    credentialsId: 'github-notifications-token',
                    sha: "${env.GIT_COMMIT}"
                )
            }
            parallel {
                stage('Backend Checks') {
                    steps {
                        dir('backend') {
                            echo "Running Backend Checks using system Poetry..."
                            sh 'poetry install --no-root'
                            
                            script {
                                sh(
                                    script: 'poetry run flake8 . --format=default > flake8_report.txt || true',
                                    returnStatus: true
                                )
                            }
                            
                            echo "Flake8 finished. Moving straight to tests..."
                            sh 'poetry run pytest --junitxml=pytest_report.xml'
                        }
                    }
                    post {
                        always {
                            recordIssues(
                                enabledForFailure: true, 
                                ignoreQualityGate: true, 
                                tools: [pyLint(id: 'flake8', name: 'Flake8', pattern: 'backend/flake8_report.txt')]
                            )
                            junit allowEmptyResults: true, testResults: 'backend/pytest_report.xml'
                        }
                    }
                }

                stage('Frontend Checks') {
                    steps {
                        dir('frontend') {
                            echo "Running Frontend Checks using system npm..."
                            sh 'npm install'
                            
                            script {
                                sh(
                                    script: 'npm run lint > eslint_report.xml || true',
                                    returnStatus: true
                                )
                            }
                            
                            echo "Linting finished. Running Vitest..."
                            sh 'npm run test:run -- --reporter=junit --outputFile=vitest_report.xml'
                        }
                    }
                    post {
                        always {
                            recordIssues(
                                enabledForFailure: true, 
                                ignoreQualityGate: true, 
                                tools: [checkStyle(id: 'eslint', name: 'ESLint', pattern: 'frontend/eslint_report.xml')]
                            )
                            junit allowEmptyResults: true, keepLongStdio: true, testResults: 'frontend/vitest_report.xml'
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            script {
                sh 'rm -f backend/flake8_report.txt backend/pytest_report.xml frontend/eslint_report.xml frontend/vitest_report.xml'
            }
        }

        success {
            githubChecks(
                name: 'CI / Push Checks',
                status: 'COMPLETED',
                conclusion: 'SUCCESS',
                summary: 'All checks passed successfully! ✅',
                detailsURL: "${env.BUILD_URL}",
                account: 'vitwits',
                repo: 'language-AI-tutor',
                credentialsId: 'github-notifications-token',
                sha: "${env.GIT_COMMIT}"
            )
        }

        failure {
            githubChecks(
                name: 'CI / Push Checks',
                status: 'COMPLETED',
                conclusion: 'FAILURE',
                summary: 'Some checks failed. Please review the logs.',
                detailsURL: "${env.BUILD_URL}",
                account: 'vitwits',
                repo: 'language-AI-tutor',
                credentialsId: 'github-notifications-token',
                sha: "${env.GIT_COMMIT}"
            )
        }

        aborted {
            githubChecks(
                name: 'CI / Push Checks',
                status: 'COMPLETED',
                conclusion: 'CANCELLED',
                summary: 'Pipeline was aborted.',
                detailsURL: "${env.BUILD_URL}",
                account: 'vitwits',
                repo: 'language-AI-tutor',
                credentialsId: 'github-notifications-token',
                sha: "${env.GIT_COMMIT}"
            )
        }
    }
}