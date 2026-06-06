// Jenkinsfile for German AI Tutor Monorepo - Push Check Pipeline
// Runs on pushes to non-main branches to perform parallel static analysis and tests.

pipeline {
    agent any // Runs on your local VM

    options {
        timeout(time: 15, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    triggers {
        pollSCM('* * * * *')
    }

    environment {
        GITHUB_STATUS_CONTEXT = 'ci/jenkins/push-check'
    }

    stages {
        stage('Guard') {
            steps {
                script {
                    // Standard Git jobs use GIT_BRANCH (e.g., "origin/main" or "origin/feature/setup-jenkins")
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
                            echo "Running Backend Static Analysis and Tests..."
                            sh 'poetry install'
                            
                            // Use tee to write to a file AND keep flake8's true exit code visible to Jenkins
                            sh 'set -o pipefail; poetry run flake8 . --format=default | tee flake8_report.txt'
                            
                            // Unit tests
                            sh 'poetry run pytest --junitxml=pytest_report.xml'
                        }
                    }
                    post {
                        always {
                            recordIssues(tools: [pyLint(id: 'flake8', name: 'Flake8', pattern: 'backend/flake8_report.txt')])
                            junit 'backend/pytest_report.xml'
                        }
                    }
                }

                stage('Frontend Checks') {
                    steps {
                        dir('frontend') {
                            echo "Running Frontend Static Analysis and Tests..."
                            sh 'npm install'
                            
                            // Static analysis - failure here will correctly stop the pipeline
                            sh 'npm run lint'
                            
                            // Unit tests
                            sh 'npm run test:run -- --reporter=junit --outputFile=vitest_report.xml'
                        }
                    }
                    post {
                        always {
                            recordIssues(tools: [checkStyle(id: 'eslint', name: 'ESLint', pattern: 'frontend/eslint_report.xml')])
                            junit 'frontend/vitest_report.xml'
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            script {
                // Cleanup artifacts to save disk space safely
                dir('backend') {
                    sh 'rm -f flake8_report.txt pytest_report.xml'
                }
                dir('frontend') {
                    sh 'rm -f eslint_report.xml vitest_report.xml'
                }
            }
        }
        success {
            githubCommitStatus(context: env.GITHUB_STATUS_CONTEXT, state: 'SUCCESS')
        }
        failure {
            githubCommitStatus(context: env.GITHUB_STATUS_CONTEXT, state: 'FAILURE')
        }
        unstable {
            githubCommitStatus(context: env.GITHUB_STATUS_CONTEXT, state: 'FAILURE')
        }
    }
}