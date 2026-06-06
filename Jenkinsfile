// Jenkinsfile for German AI Tutor Monorepo - Host-based Push Check Pipeline
pipeline {
    agent any // Runs directly on the host machine using Poetry and npm installed via Ansible

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
                    steps {
                        dir('frontend') {
                            echo "Running Frontend Checks using system npm..."
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

    // Global pipeline post actions for cleanup and GitHub notifications
    post {
        always {
            script {
                dir('backend') { sh 'rm -f flake8_report.txt pytest_report.xml' }
                dir('frontend') { sh 'rm -f eslint_report.xml vitest_report.xml' }
            }
        }
        success {
            githubNotify context: 'ci/jenkins/push-check', status: 'SUCCESS', description: 'All checks passed successfully!'
        }
        failure {
            githubNotify context: 'ci/jenkins/push-check', status: 'FAILURE', description: 'Pipeline checks failed.'
        }
    }
}