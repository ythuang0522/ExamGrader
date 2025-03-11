document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('uploadForm');
    const progressSection = document.getElementById('progressSection');
    const resultsSection = document.getElementById('resultsSection');
    const progressBar = document.getElementById('progressBar');
    const progressCount = document.getElementById('progressCount');
    const progressPercentage = document.getElementById('progressPercentage');
    const progressStatus = document.getElementById('progressStatus');
    const totalScore = document.getElementById('totalScore');
    const questionNav = document.getElementById('questionNav');
    const questionResults = document.getElementById('questionResults');

    let pollInterval;

    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(uploadForm);
        
        try {
            progressSection.classList.remove('hidden');
            resultsSection.classList.add('hidden');
            
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error('Upload failed');
            }
            
            // Start polling for progress
            pollInterval = setInterval(checkProgress, 1000);
            
        } catch (error) {
            alert('Error uploading files: ' + error.message);
        }
    });

    async function checkProgress() {
        try {
            const response = await fetch('/progress');
            const data = await response.json();
            
            updateProgress(data);
            
            if (data.is_complete) {
                clearInterval(pollInterval);
                if (data.results) {
                    displayResults(data.results);
                }
            }
        } catch (error) {
            console.error('Error checking progress:', error);
        }
    }

    function updateProgress(data) {
        const { total_questions, graded_questions, current_status } = data;
        const percentage = total_questions ? Math.round((graded_questions / total_questions) * 100) : 0;
        
        progressBar.style.width = `${percentage}%`;
        progressCount.textContent = `${graded_questions}/${total_questions} Questions`;
        progressPercentage.textContent = `${percentage}%`;
        progressStatus.textContent = current_status;
    }

    function displayResults(results) {
        resultsSection.classList.remove('hidden');
        
        // Display total score
        const scorePercentage = Math.round((results.total_score / results.max_possible) * 100);
        totalScore.innerHTML = `
            <div class="text-center">
                <div class="text-3xl font-bold ${scorePercentage >= 70 ? 'text-green-600' : 'text-red-600'}">
                    ${results.total_score}/${results.max_possible}
                </div>
                <div class="text-gray-600">${scorePercentage}%</div>
            </div>
        `;

        // Clear previous results
        questionNav.innerHTML = '';
        questionResults.innerHTML = '';

        // Sort questions to maintain proper order (e.g., 1, 2, 3a, 3b, 3c, 4, etc.)
        const sortedQuestions = Object.entries(results.question_results).sort((a, b) => {
            const aMatch = a[0].match(/(\d+)([a-z])?/i);
            const bMatch = b[0].match(/(\d+)([a-z])?/i);
            
            if (!aMatch || !bMatch) return 0;
            
            const aNum = parseInt(aMatch[1]);
            const bNum = parseInt(bMatch[1]);
            
            if (aNum !== bNum) {
                return aNum - bNum;
            }
            
            // If main numbers are the same, sort by subproblem letter
            const aLetter = aMatch[2] || '';
            const bLetter = bMatch[2] || '';
            return aLetter.localeCompare(bLetter);
        });

        // Display each question result
        sortedQuestions.forEach(([questionId, result]) => {
            const scorePercent = Math.round((result.score / result.max_score) * 100);
            const scoreColor = scorePercent >= 70 ? 'text-green-600' : 'text-red-600';

            // Format question number (e.g., "Question 3a" or "Question 5")
            const formattedQuestionId = questionId.replace(/^(\d+)([a-z])?$/i, 'Question $1$2');

            // Add navigation link
            const navButton = document.createElement('button');
            navButton.className = `w-full text-left p-2 rounded hover:bg-gray-200 flex justify-between items-center ${scoreColor}`;
            navButton.innerHTML = `
                <span>${formattedQuestionId}</span>
                <span class="font-bold">${result.score}/${result.max_score}</span>
            `;
            navButton.onclick = () => scrollToQuestion(`question-${questionId}`);
            questionNav.appendChild(navButton);

            // Add detailed result
            const resultDiv = document.createElement('div');
            resultDiv.id = `question-${questionId}`;
            resultDiv.className = 'bg-gray-50 rounded-lg p-6 transition-all duration-300';
            resultDiv.innerHTML = `
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-xl font-bold">${formattedQuestionId}</h3>
                    <div class="text-xl ${scoreColor} font-bold">${result.score}/${result.max_score}</div>
                </div>
                <div class="space-y-4">
                    <div class="bg-white p-4 rounded-lg">
                        <h4 class="font-bold text-gray-700 mb-2">Question:</h4>
                        <div class="text-gray-600">${result.question}</div>
                    </div>
                    ${result.rubric && result.rubric !== 'No rubric available' ? `
                        <div class="bg-white p-4 rounded-lg">
                            <h4 class="font-bold text-gray-700 mb-2">Grading Rubric:</h4>
                            <div class="text-gray-600">${result.rubric}</div>
                        </div>
                    ` : ''}
                    <div class="bg-white p-4 rounded-lg">
                        <h4 class="font-bold text-gray-700 mb-2">Student's Answer:</h4>
                        <div class="text-gray-600">${result.student_answer}</div>
                    </div>
                    <div class="bg-white p-4 rounded-lg">
                        <h4 class="font-bold text-gray-700 mb-2">Correct Answer:</h4>
                        <div class="text-gray-600">${result.correct_answer}</div>
                    </div>
                    <div class="bg-white p-4 rounded-lg">
                        <h4 class="font-bold text-gray-700 mb-2">Grading Explanation:</h4>
                        <div class="text-gray-600">${result.reason || 'No explanation available'}</div>
                    </div>
                </div>
            `;
            questionResults.appendChild(resultDiv);
        });
    }
}); 