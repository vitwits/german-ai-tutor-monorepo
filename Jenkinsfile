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
            parallel {
                stage('Backend Checks') {
                    steps {
                        dir('backend') {
                            echo "Running Backend Checks using system Poetry..."
                            sh 'poetry install --no-root'
                            
                            script {
                                sh(
                                    script: '#!/bin/bash\nset -o pipefail; poetry run flake8 . --format=default | tee flake8_report.txt',
                                    returnStatus: true
                                )
                            }
                            
                            echo "Flake8 finished. Moving straight to tests..."
                            sh 'poetry run pytest --junitxml=pytest_report.xml'
                        }
                    }
                    post {
                        always {
                            recordIssues(enabledForFailure: true, tools: [pyLint(id: 'flake8', name: 'Flake8', pattern: 'backend/flake8_report.txt')])
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
                                    script: '#!/bin/bash\nset -o pipefail; npm run lint | tee eslint_report.xml',
                                    returnStatus: true
                                )
                            }
                            
                            echo "Linting finished. Running Vitest..."
                            sh 'npm run test:run -- --reporter=junit --outputFile=vitest_report.xml'
                        }
                    }
                    post {
                        always {
                            recordIssues(enabledForFailure: true, tools: [checkStyle(id: 'eslint', name: 'ESLint', pattern: 'frontend/eslint_report.xml')])
                            junit allowEmptyResults: true, testResults: 'frontend/vitest_report.xml'
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            script {
                dir('backend') { sh 'rm -f flake8_report.txt pytest_report.xml' }
                dir('frontend') { sh 'rm -f eslint_report.xml vitest_report.xml' }
            }
        }
        success {
            script {
                try {
                    githubNotify context: 'ci/jenkins/push-check', 
                                 status: 'SUCCESS', 
                                 description: 'All checks passed successfully!',
                                 account: 'vitwits',
                                 repo: 'language-AI-tutor',
                                 credentialsId: 'jenkins-github-ai-tutor',
                                 sha: "${env.GIT_COMMIT}"
                } catch (Exception e) {
                    echo "Warning: Failed to send GitHub notification: ${e.message}"
                }
            }
        }
        failure {
            script {
                try {
                    githubNotify context: 'ci/jenkins/push-check', 
                                 status: 'FAILURE', 
                                 description: 'Pipeline checks failed.',
                                 account: 'vitwits',
                                 repo: 'language-AI-tutor',
                                 credentialsId: 'jenkins-github-ai-tutor',
                                 sha: "${env.GIT_COMMIT}"
                } catch (Exception e) {
                    echo "Warning: Failed to send GitHub notification: ${e.message}"
                }
            }
        }
    }
}