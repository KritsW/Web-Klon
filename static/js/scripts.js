let typingTimer;
const typingDelay = 1500;  // 1.5 seconds delay
const textarea = document.getElementById('text');
const loadingContainer = document.getElementById('loading-container');
const loadingBar = document.getElementById('loading-bar');
const loadingText = document.getElementById('loading-text');
const rhymeMessagesDiv = document.getElementById('rhyme-messages');
const syllableListsDiv = document.getElementById('syllable-lists');

document.addEventListener('DOMContentLoaded', function() {
    textarea.addEventListener('input', function() {
        clearTimeout(typingTimer);
        typingTimer = setTimeout(fetchSuggestions, typingDelay);
    });
});

async function fetchSuggestions() {
    const text = textarea.value;
    if (text.length > 0) {
        showLoading();
        const response = await fetch('/check_rhyme', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: `text=${encodeURIComponent(text)}`
        });
        const data = await response.json();
        hideLoading();
        rhymeMessagesDiv.innerHTML = '<h2>คำที่ไม่สัมผัส:</h2><ul>' + data.messages.map(message => `<li>${message}</li>`).join('') + '</ul>';
        rhymeMessagesDiv.innerHTML += `<p>Word Count: ${data.word_count} words</p>`;
        rhymeMessagesDiv.innerHTML += `<p>Processing time: ${data.processing_time.toFixed(2)} seconds</p>`;

        syllableListsDiv.innerHTML = data.display_words.map((wordInfo, index) => {
            const [word_pair, rhymes] = wordInfo;
            const status = rhymes ? 'highlight-green' : 'highlight-red';
            return `<div class="${status}">${word_pair}</div>`;
        }).join('');
    } else {
        rhymeMessagesDiv.innerHTML = '';
        syllableListsDiv.innerHTML = '';
    }
}

function showLoading() {
    loadingContainer.style.display = 'block';
    loadingBar.style.width = '0';
    setTimeout(() => {
        loadingBar.style.width = '100%';
    }, 100);
}

function hideLoading() {
    loadingContainer.style.display = 'none';
    loadingBar.style.width = '0';
}

// Change style of navbar on scroll
window.onscroll = function() {myFunction()};
function myFunction() {
    var navbar = document.getElementById("myNavbar");
    if (document.body.scrollTop > 100 || document.documentElement.scrollTop > 100) {
        navbar.className = "w3-bar" + " w3-card" + " w3-animate-top" + " w3-white";
    } else {
        navbar.className = navbar.className.replace(" w3-card w3-animate-top w3-white", "");
    }
}

// Used to toggle the menu on small screens when clicking on the menu button
function toggleFunction() {
    var x = document.getElementById("navDemo");
    if (x.className.indexOf("w3-show") == -1) {
        x.className += " w3-show";
    } else {
        x.className = x.className.replace(" w3-show", "");
    }
}
