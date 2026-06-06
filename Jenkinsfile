// Jenkinsfile for German AI Tutor Monorepo - Docker-based Push Check Pipeline
pipeline {
    agent none // Individual stages define their own runtime containers

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
            agent any // Runs natively on the base Jenkins executor node
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
                    agent {
                        docker {
                            image 'python:3.12-slim'
                            reuseNode true
                        }
                    }
                    steps {
                        dir('backend') {
                            echo "Running Backend Checks..."
                            sh 'pip install poetry'
                            sh 'poetry install'
                            sh 'set -o pipefail; poetry run flake8 . --format=default | tee flake8_report.txt'
                            sh 'poetry run pytest --junitxml=pytest_report.xml'
                        }
                    }
                    post {
                        always {
                            recordIssues(tools: [pyLint(id: 'flake8', name: 'Flake8', pattern: 'backend/flake8_report.txt')])
                            junit allowEmptyResults: true, testResults: 'backend/pytest_report.xml'
                        }
                    }
                }

                stage('Frontend Checks') {
                    agent {
                        docker {
                            image 'node:20-slim'
                            reuseNode true
                        }
                    }
                    steps {
                        dir('frontend') {
                            echo "Running Frontend Checks..."
                            sh 'npm install'
                            sh 'npm run lint'
                            sh 'npm run test:run -- --reporter=junit --outputFile=vitest_report.xml'
                        }
                    }
                    post {
                        always {
                            recordIssues(tools: [checkStyle(id: 'eslint', name: 'ESLint', pattern: 'frontend/eslint_report.xml')])
                            junit allowEmptyResults: true, testResults: 'frontend/vitest_report.xml'
                        }
                    }
                }
            }
        }
    }

    // Global pipeline post actions run at the very end
    post {
        always {
            // Force execution back onto a standard agent node to run cleanup commands safely
            node('built-in' || 'master' || 'any') {
                script {
                    dir('backend') { sh 'rm -f flake8_report.txt pytest_report.xml' }
                    dir('frontend') { sh 'rm -f eslint_report.xml vitest_report.xml' }
                }
            }
        }
        success {
            node('built-in' || 'master' || 'any') {
                githubNotify context: 'ci/jenkins/push-check', status: 'SUCCESS', description: 'All checks passed successfully!'
            }
        }
        failure {
            node('built-in' || 'master' || 'any') {
                githubNotify context: 'ci/jenkins/push-check', status: 'FAILURE', description: 'Pipeline checks failed.'
            }
        }
    }
}