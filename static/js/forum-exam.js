var examRules;
var examTimer = 10;

function showExam()
{
    var submitForm = document.getElementById('submitForm');
    var examForm = document.getElementById('examForm');
    if (!examRules || !examRules.length) {
        submitForm.style.display = 'block';
        return;
    }
    examForm.style.display = 'block';
    showExamRule();
}

function showExamRule()
{
    var submitForm = document.getElementById('submitForm');
    var examForm = document.getElementById('examForm');
    var rule = examRules[0];
    examRules.splice(0, 1);
    var tr = document.createElement('TR');
    var td = document.createElement('TD');
    td.className = 'forum-exam-question';
    td.innerHTML = '<h1>' + rule.question + '</h1>';
    tr.appendChild(td);
    td = document.createElement('TD');
    td.className = 'forum-exam-answers';
    var counter = document.createElement('SPAN');
    counter.className = 'forum-exam-counter';
    counter.innerHTML = examTimer;
    var cnt = examTimer;
    td.appendChild(counter);
    tr.appendChild(td);
    var examTable = document.getElementById('examTable');
    examTable.appendChild(tr);
    var timerEvent = function () {
        cnt--;
        counter.innerHTML = cnt;
        if (cnt == 0) {
            td.innerHTML = '';
            var answers = [];
            /* Correct answer */
            var button = document.createElement('button');
            button.innerHTML = rule.correct_answer;
            button.onclick = function () {
                td.innerHTML = rule.correct_answer;
                if (examRules.length) {
                    showExamRule();
                } else {
                    examForm.style.display = 'none';
                    var hidden = document.createElement('INPUT');
                    hidden.type = 'hidden';
                    hidden.name = 'passed';
                    hidden.value = '1';
                    var els = submitForm.getElementsByTagName('FORM');
                    els[0].appendChild(hidden);
                    els[0].submit();
                }
            };
            answers.push(button);
            /* Incorrect answers */
            for (var i = 0; i < rule.incorrect_answers.length; i++) {
                (function (i) {
                    var button = document.createElement('button');
                    button.innerHTML = rule.incorrect_answers[i];
                    button.onclick = function () {
                        td.innerHTML = rule.incorrect_answers[i];
                        var hidden = document.createElement('INPUT');
                        hidden.type = 'hidden';
                        hidden.name = 'failed';
                        hidden.value = '1';
                        var els = submitForm.getElementsByTagName('FORM');
                        els[0].appendChild(hidden);
                        els[0].submit();
                    };
                    answers.push(button);
                })(i);
            }
            /* Shuffle and display answers */
            shuffle(answers);
            for (var i = 0; i < answers.length; i++) {
                td.appendChild(answers[i]);
            }
        } else {
            setTimeout(timerEvent, 1000);
        }
    };
    setTimeout(timerEvent, 1000);
}

function shuffle(o)
{
    for (var j, x, i = o.length; i; j = parseInt(Math.random() * i), x = o[--i], o[i] = o[j], o[j] = x);
    return o;
};
