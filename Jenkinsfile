// Jenkinsfile for German AI Tutor Monorepo
pipeline {
    agent any

    environment {
        GEMINI_API_KEY = credentials('GEMINI_API_KEY_SECRET')
        NEXUS_REGISTRY = 'localhost:8082'
        APP_VERSION    = "1.0.${env.BUILD_NUMBER}"
        NEXUS_CREDS    = credentials('NEXUS_CREDENTIALS_ID')
    }

    options {
        timeout(time: 15, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    triggers {
        pollSCM('H * * * *') // Перевірка щогодини
    }

    stages {
        stage('Guard') {
            steps {
                script {
                    def branchName = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ""
                    echo "Processing branch: ${branchName}"
                }
            }
        }

        stage('Parallel Checks') {
            // ПРОСТО І ЗРОЗУМІЛО: ловить будь-яку гілку, де є /feature/
            when { branch wildcard: "**/feature/**", comparator: "EQUALS" }
            
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
                            sh 'npm run test:run -- --reporter=default --reporter=junit --outputFile=vitest_report.xml'
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

        stage('Release (Tests + Build + Push)') {
            // ПРОСТО І ЗРОЗУМІЛО: ловить і main, і origin/main
            when { branch wildcard: "**/main", comparator: "EQUALS" }
            
            stages {
                stage('Final Validation') {
                    parallel {
                        stage('Backend Test') {
                            steps {
                                dir('backend') {
                                    sh 'poetry install --no-root'
                                    sh 'poetry run pytest --junitxml=pytest_report.xml'
                                }
                            }
                        }
                        stage('Frontend Test') {
                            steps {
                                dir('frontend') {
                                    sh 'npm install'
                                    sh 'npm run test:run -- --reporter=junit --outputFile=vitest_report.xml'
                                }
                            }
                        }
                    }
                    post {
                        always {
                            junit allowEmptyResults: true, testResults: '**/pytest_report.xml, **/vitest_report.xml'
                        }
                    }
                }

                stage('Build and Push Docker Images') {
                    steps {
                        script {
                            sh "echo ${NEXUS_CREDS_PSW} | docker login -u ${NEXUS_CREDS_USR} --password-stdin ${NEXUS_REGISTRY}"
                            
                            // Бекенд
                            dir('backend') {
                                def backendImage = "${NEXUS_REGISTRY}/german-tutor-backend"
                                sh "docker build -t ${backendImage}:${APP_VERSION} -t ${backendImage}:latest ."
                                sh "docker push ${backendImage}:${APP_VERSION}"
                                sh "docker push ${backendImage}:latest"
                            }
                            
                            // Фронтенд
                            dir('frontend') {
                                def frontendImage = "${NEXUS_REGISTRY}/german-tutor-frontend"
                                sh "docker build -t ${frontendImage}:${APP_VERSION} -t ${frontendImage}:latest ."
                                sh "docker push ${frontendImage}:${APP_VERSION}"
                                sh "docker push ${frontendImage}:latest"
                            }
                        }
                    }
                    post {
                        always {
                            sh "docker logout ${NEXUS_REGISTRY}"
                            sh "docker rmi ${NEXUS_REGISTRY}/german-tutor-backend:${APP_VERSION} ${NEXUS_REGISTRY}/german-tutor-backend:latest || true"
                            sh "docker rmi ${NEXUS_REGISTRY}/german-tutor-frontend:${APP_VERSION} ${NEXUS_REGISTRY}/german-tutor-frontend:latest || true"
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
            publishChecks(
                name: 'CI / Push Checks',
                summary: 'All checks passed successfully! ✅',
                conclusion: 'SUCCESS',
                detailsURL: "${env.BUILD_URL}"
            )
        }

        failure {
            publishChecks(
                name: 'CI / Push Checks',
                summary: 'Some checks failed. Please review the logs.',
                conclusion: 'FAILURE',
                detailsURL: "${env.BUILD_URL}"
            )
        }

        aborted {
            publishChecks(
                name: 'CI / Push Checks',
                summary: 'Pipeline was aborted.',
                conclusion: 'CANCELED',
                detailsURL: "${env.BUILD_URL}"
            )
        }
    }
}