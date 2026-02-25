// Audio Recording and Speech Recognition for Reading Practice
class AudioRecorder {
    constructor() {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.audioBlob = null;
        this.isRecording = false;
        this.recognition = null;
        this.expectedWords = [];
        this.recognizedText = '';
        this.audioContext = null;
        this.analyser = null;
        this.visualizerCanvas = null;
        this.visualizerCtx = null;
        this.isAdvancing = false;  // Prevent rapid multiple advances

        // Detect API base path (handles both standalone /api and unified /reading/api)
        this.apiBase = this.detectApiBase();

        // Homophone dictionary - words that sound the same but have different spellings
        // For reading tests, if the spoken word is a homophone of the expected word, it counts as correct
        this.homophones = {
            // Common homophones
            'to': ['too', 'two'],
            'too': ['to', 'two'],
            'two': ['to', 'too'],
            'there': ['their', 'they\'re', 'theyre'],
            'their': ['there', 'they\'re', 'theyre'],
            'they\'re': ['there', 'their', 'theyre'],
            'theyre': ['there', 'their', 'they\'re'],
            'here': ['hear'],
            'hear': ['here'],
            'your': ['you\'re', 'youre'],
            'you\'re': ['your', 'youre'],
            'youre': ['your', 'you\'re'],
            'its': ['it\'s', 'its'],
            'it\'s': ['its'],
            'no': ['know'],
            'know': ['no'],
            'new': ['knew', 'gnu'],
            'knew': ['new', 'gnu'],
            'write': ['right', 'rite'],
            'right': ['write', 'rite'],
            'rite': ['write', 'right'],
            'see': ['sea'],
            'sea': ['see'],
            'be': ['bee'],
            'bee': ['be'],
            'by': ['buy', 'bye'],
            'buy': ['by', 'bye'],
            'bye': ['by', 'buy'],
            'for': ['four', 'fore'],
            'four': ['for', 'fore'],
            'fore': ['for', 'four'],
            'one': ['won'],
            'won': ['one'],
            'sun': ['son'],
            'son': ['sun'],
            'wait': ['weight'],
            'weight': ['wait'],
            'ate': ['eight'],
            'eight': ['ate'],
            'would': ['wood'],
            'wood': ['would'],
            'meet': ['meat'],
            'meat': ['meet'],
            'piece': ['peace'],
            'peace': ['piece'],
            'week': ['weak'],
            'weak': ['week'],
            'pair': ['pear', 'pare'],
            'pear': ['pair', 'pare'],
            'pare': ['pair', 'pear'],
            'bare': ['bear'],
            'bear': ['bare'],
            'wear': ['where', 'ware'],
            'where': ['wear', 'ware'],
            'ware': ['wear', 'where'],
            'weather': ['whether'],
            'whether': ['weather'],
            'flour': ['flower'],
            'flower': ['flour'],
            'break': ['brake'],
            'brake': ['break'],
            'made': ['maid'],
            'maid': ['made'],
            'tale': ['tail'],
            'tail': ['tale'],
            'sale': ['sail'],
            'sail': ['sale'],
            'male': ['mail'],
            'mail': ['male'],
            'pale': ['pail'],
            'pail': ['pale'],
            'plane': ['plain'],
            'plain': ['plane'],
            'main': ['mane', 'maine'],
            'mane': ['main', 'maine'],
            'rain': ['reign', 'rein'],
            'reign': ['rain', 'rein'],
            'rein': ['rain', 'reign'],
            'role': ['roll'],
            'roll': ['role'],
            'hole': ['whole'],
            'whole': ['hole'],
            'soul': ['sole'],
            'sole': ['soul'],
            'dear': ['deer'],
            'deer': ['dear'],
            'steal': ['steel'],
            'steel': ['steal'],
            'heel': ['heal', 'he\'ll'],
            'heal': ['heel', 'he\'ll'],
            'been': ['bin'],
            'bin': ['been'],
            'in': ['inn'],
            'inn': ['in'],
            'threw': ['through', 'thru'],
            'through': ['threw', 'thru'],
            'thru': ['threw', 'through'],
            'blue': ['blew'],
            'blew': ['blue'],
            'do': ['due', 'dew'],
            'due': ['do', 'dew'],
            'dew': ['do', 'due'],
            'nose': ['knows'],
            'knows': ['nose'],
            'rows': ['rose'],
            'rose': ['rows'],
            'toes': ['tows'],
            'tows': ['toes'],
            'red': ['read'],
            'read': ['red', 'reed'],
            'reed': ['read'],
            'led': ['lead'],
            'lead': ['led'],
            'night': ['knight'],
            'knight': ['night'],
            'not': ['knot'],
            'knot': ['not'],
            'which': ['witch'],
            'witch': ['which'],
            'flour': ['flower'],
            'flower': ['flour'],
            'hour': ['our'],
            'our': ['hour'],
            'eye': ['i', 'aye'],
            'i': ['eye', 'aye'],
            'aye': ['eye', 'i'],
            'die': ['dye'],
            'dye': ['die'],
            'tide': ['tied'],
            'tied': ['tide'],
            'side': ['sighed'],
            'sighed': ['side'],
            'board': ['bored'],
            'bored': ['board'],
            'cord': ['chord'],
            'chord': ['cord'],
            'scene': ['seen'],
            'seen': ['scene'],
            'seem': ['seam'],
            'seam': ['seem'],
            'feet': ['feat'],
            'feat': ['feet'],
            'peek': ['peak', 'pique'],
            'peak': ['peek', 'pique'],
            'pique': ['peek', 'peak'],
            'creek': ['creak'],
            'creak': ['creek'],
            'steak': ['stake'],
            'stake': ['steak'],
            'great': ['grate'],
            'grate': ['great'],
            'cite': ['site', 'sight'],
            'site': ['cite', 'sight'],
            'sight': ['cite', 'site'],
            'cents': ['sense', 'scents'],
            'sense': ['cents', 'scents'],
            'scents': ['cents', 'sense'],
            'altar': ['alter'],
            'alter': ['altar'],
            'capital': ['capitol'],
            'capitol': ['capital'],
            'principal': ['principle'],
            'principle': ['principal'],
            'stationary': ['stationery'],
            'stationery': ['stationary'],
            'course': ['coarse'],
            'coarse': ['course'],
            'morning': ['mourning'],
            'mourning': ['morning'],
            'waist': ['waste'],
            'waste': ['waist'],
            'wait': ['weight'],
            'weight': ['wait'],
            'root': ['route'],
            'route': ['root'],
            'threw': ['through'],
            'through': ['threw'],
            'aloud': ['allowed'],
            'allowed': ['aloud'],
            'affect': ['effect'],
            'effect': ['affect'],
            'accept': ['except'],
            'except': ['accept'],
            'a': ['uh'],
            'uh': ['a'],
            'an': ['and'],
            'and': ['an'],
            'the': ['duh', 'da'],
            'duh': ['the'],
            'da': ['the']
        };

        // Near-matches: words that sound very similar but aren't homophones
        // Used for words that speech recognition commonly confuses
        this.nearMatches = {
            'tube': ['tub', 'tubes'],
            'tub': ['tube'],
            'tubes': ['tube', 'tubs'],
            'tubs': ['tubes'],
            'cube': ['cub'],
            'cub': ['cube'],
            'robe': ['rob'],
            'rob': ['robe'],
            'globe': ['glob'],
            'glob': ['globe'],
            'probe': ['prob'],
            'lobe': ['lob'],
            'lob': ['lobe']
        };

        // Track recognition health
        this.wordsSinceReset = 0;
        this.maxWordsBeforeReset = 15;  // Reset recognition every 15 words to prevent degradation

        // Number words to digits mapping for speech recognition
        // When user says "thirteen", it should match "13" displayed on screen
        this.numberWords = {
            // Basic numbers 0-20
            'zero': '0', 'oh': '0', 'o': '0',
            'one': '1', 'won': '1',
            'two': '2', 'to': '2', 'too': '2',
            'three': '3',
            'four': '4', 'for': '4', 'fore': '4',
            'five': '5',
            'six': '6',
            'seven': '7',
            'eight': '8', 'ate': '8',
            'nine': '9',
            'ten': '10',
            'eleven': '11',
            'twelve': '12',
            'thirteen': '13',
            'fourteen': '14',
            'fifteen': '15',
            'sixteen': '16',
            'seventeen': '17',
            'eighteen': '18',
            'nineteen': '19',
            'twenty': '20',
            // Tens
            'thirty': '30',
            'forty': '40', 'fourty': '40',
            'fifty': '50',
            'sixty': '60',
            'seventy': '70',
            'eighty': '80',
            'ninety': '90',
            // Common compound numbers (21-99)
            'twenty one': '21', 'twenty-one': '21', 'twentyone': '21',
            'twenty two': '22', 'twenty-two': '22', 'twentytwo': '22',
            'twenty three': '23', 'twenty-three': '23', 'twentythree': '23',
            'twenty four': '24', 'twenty-four': '24', 'twentyfour': '24',
            'twenty five': '25', 'twenty-five': '25', 'twentyfive': '25',
            'twenty six': '26', 'twenty-six': '26', 'twentysix': '26',
            'twenty seven': '27', 'twenty-seven': '27', 'twentyseven': '27',
            'twenty eight': '28', 'twenty-eight': '28', 'twentyeight': '28',
            'twenty nine': '29', 'twenty-nine': '29', 'twentynine': '29',
            'thirty one': '31', 'thirty-one': '31', 'thirtyone': '31',
            'thirty two': '32', 'thirty-two': '32', 'thirtytwo': '32',
            'thirty three': '33', 'thirty-three': '33', 'thirtythree': '33',
            'thirty four': '34', 'thirty-four': '34', 'thirtyfour': '34',
            'thirty five': '35', 'thirty-five': '35', 'thirtyfive': '35',
            'thirty six': '36', 'thirty-six': '36', 'thirtysix': '36',
            'thirty seven': '37', 'thirty-seven': '37', 'thirtyseven': '37',
            'thirty eight': '38', 'thirty-eight': '38', 'thirtyeight': '38',
            'thirty nine': '39', 'thirty-nine': '39', 'thirtynine': '39',
            // Larger numbers
            'hundred': '100', 'one hundred': '100',
            'thousand': '1000', 'one thousand': '1000',
            'million': '1000000', 'one million': '1000000'
        };

        // Reverse mapping: digits to number words (for matching "13" to "thirteen")
        this.digitsToWords = {};
        for (const [word, digit] of Object.entries(this.numberWords)) {
            if (!this.digitsToWords[digit]) {
                this.digitsToWords[digit] = [];
            }
            this.digitsToWords[digit].push(word);
        }

        this.init();
    }

    detectApiBase() {
        const path = window.location.pathname;
        if (path.startsWith('/reading')) {
            return '/reading/api';
        }
        return '/api';
    }

    init() {
        // Setup UI elements
        this.recordBtn = document.getElementById('record-btn');
        this.stopBtn = document.getElementById('stop-record-btn');
        this.playBtn = document.getElementById('play-recording-btn');
        this.statusEl = document.getElementById('recording-status');
        this.feedbackEl = document.getElementById('recording-feedback');
        this.playbackEl = document.getElementById('recording-playback');
        this.visualizerEl = document.getElementById('recording-visualizer');
        this.visualizerCanvas = document.getElementById('audio-visualizer');
        this.autoStartEnabled = true; // Auto-start recording by default

        // Microphone test elements
        this.testMicBtn = document.getElementById('test-mic-btn');
        this.micTestSection = document.getElementById('mic-test-section');
        this.startTestBtn = document.getElementById('start-mic-test');
        this.stopTestBtn = document.getElementById('stop-mic-test');
        this.closeTestBtn = document.getElementById('close-mic-test');
        this.volumeMeter = document.getElementById('volume-meter');
        this.detectedSpeechEl = document.getElementById('detected-speech');
        this.micTestStatus = document.getElementById('mic-test-status');
        this.isTestingMic = false;
        this.testStream = null;
        this.testRecognition = null;

        // Check if recording is supported
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.updateStatus('⚠️ Audio recording not supported on this device/browser');
            if (this.recordBtn) {
                this.recordBtn.disabled = true;
                this.recordBtn.textContent = '🔴 Recording Not Supported';
            }
            return;
        }

        // Check for HTTPS (required for microphone on iOS)
        if (window.location.protocol !== 'https:' && window.location.hostname !== 'localhost') {
            console.warn('Microphone access requires HTTPS. Recording may not work.');
        }

        // Setup event listeners
        this.recordBtn?.addEventListener('click', () => this.toggleRecording());
        this.stopBtn?.addEventListener('click', () => this.stopRecording());
        this.playBtn?.addEventListener('click', () => this.playRecording());

        // Microphone test listeners
        this.testMicBtn?.addEventListener('click', () => this.showMicTest());
        this.startTestBtn?.addEventListener('click', () => this.startMicTest());
        this.stopTestBtn?.addEventListener('click', () => this.stopMicTest());
        this.closeTestBtn?.addEventListener('click', () => this.closeMicTest());

        // Initialize Web Speech API if available
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = true;
            this.recognition.interimResults = true;
            this.recognition.lang = 'en-US';

            this.recognition.onresult = (event) => {
                // Only process if not currently advancing to next word
                if (this.isAdvancing) return;

                let currentTranscript = '';

                // Get the most recent result only (not accumulating)
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    currentTranscript = event.results[i][0].transcript;
                }

                // Store only the current word being spoken (not accumulating history)
                this.recognizedText = currentTranscript.trim();

                // Update compact speech feedback panel
                const speechPanel = document.getElementById('live-speech-text');
                if (speechPanel && this.recognizedText) {
                    speechPanel.textContent = this.recognizedText;
                }

                // Real-time word synchronization - one word at a time
                if (this.recognizedText) {
                    this.syncWordsWithSpeech(this.recognizedText);
                }
            };

            this.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                this.updateStatus('Speech recognition error: ' + event.error);
            };
        }

        // Setup audio visualizer
        if (this.visualizerCanvas) {
            this.visualizerCtx = this.visualizerCanvas.getContext('2d');
        }
    }

    toggleRecording() {
        if (this.isRecording) {
            this.stopRecording();
        } else {
            this.startRecording();
        }
    }

    async startRecording(isAutoStart = false) {
        try {
            // Get current words being displayed
            this.expectedWords = this.getCurrentWords();

            // Check for MediaRecorder support
            if (typeof MediaRecorder === 'undefined') {
                throw new Error('MediaRecorder not supported. Please use Safari 14.1+ on iOS or Chrome on desktop.');
            }

            // Simplified constraints for better iOS compatibility
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // Setup audio context for visualization
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = this.audioContext.createMediaStreamSource(stream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            source.connect(this.analyser);

            // Start visualizer
            this.startVisualizer();

            // Setup MediaRecorder with iOS-compatible options
            let recorderOptions = {};

            // Check supported MIME types
            const mimeTypes = [
                'audio/webm;codecs=opus',
                'audio/webm',
                'audio/mp4',
                'audio/mpeg',
                'audio/wav'
            ];

            for (const mimeType of mimeTypes) {
                if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(mimeType)) {
                    recorderOptions.mimeType = mimeType;
                    console.log('Using MIME type:', mimeType);
                    break;
                }
            }

            // Create MediaRecorder - iOS Safari may not support options
            try {
                this.mediaRecorder = new MediaRecorder(stream, recorderOptions);
            } catch (e) {
                console.log('Failed with options, trying without:', e);
                this.mediaRecorder = new MediaRecorder(stream);
            }
            this.audioChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };

            this.mediaRecorder.onstop = () => {
                const blobType = recorderOptions.mimeType || 'audio/mp4';
                this.audioBlob = new Blob(this.audioChunks, { type: blobType });
                const audioUrl = URL.createObjectURL(this.audioBlob);
                this.playbackEl.src = audioUrl;

                // Stop all tracks
                stream.getTracks().forEach(track => track.stop());

                // Analyze the recording
                this.analyzeRecording();
            };

            // Start recording
            this.mediaRecorder.start();
            this.isRecording = true;

            // Start speech recognition
            if (this.recognition) {
                this.recognizedText = '';
                this.recognition.start();
            }

            // Update UI
            if (this.recordBtn) {
                this.recordBtn.textContent = '⏹ Stop Recording';
                this.recordBtn.classList.add('recording-active');
            }

            // Show speech feedback panel
            const speechPanel = document.getElementById('speech-feedback-panel');
            if (speechPanel) {
                speechPanel.style.display = 'block';
            }

            // Show recording indicator
            const recIndicator = document.getElementById('recording-indicator');
            if (recIndicator) {
                recIndicator.style.display = 'inline';
            }

            // Show compact recording status
            const statusBar = document.getElementById('recording-status-bar');
            if (statusBar) {
                statusBar.style.display = 'block';
            }

            this.updateStatus('🔴 Recording...');

            // Play sound effect
            if (window.soundManager) {
                window.soundManager.playClick();
            }

        } catch (error) {
            console.error('Error starting recording:', error);

            // Provide specific error messages
            let errorMessage = 'Error: Could not access microphone. ';

            if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
                errorMessage = '🎤 Microphone access denied. Please allow microphone permissions in your browser settings.';

                // iOS Safari specific message
                if (/iPad|iPhone|iPod/.test(navigator.userAgent)) {
                    errorMessage += ' On iOS: Settings > Safari > Microphone > Allow';
                }
            } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
                errorMessage = '🎤 No microphone found. Please connect a microphone.';
            } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
                errorMessage = '🎤 Microphone is already in use by another app.';
            } else if (error.name === 'OverconstrainedError' || error.name === 'ConstraintNotSatisfiedError') {
                errorMessage = '🎤 Microphone settings not supported.';
            } else if (error.name === 'TypeError') {
                errorMessage = '⚠️ HTTPS required. Audio recording requires a secure connection (HTTPS).';
            }

            this.updateStatus(errorMessage);
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;

            if (this.recognition) {
                this.recognition.stop();
            }

            // Stop visualizer
            this.stopVisualizer();

            // Update UI
            if (this.recordBtn) {
                this.recordBtn.textContent = '🎤 Record';
                this.recordBtn.classList.remove('recording-active');
            }

            // Hide speech feedback panel after delay
            setTimeout(() => {
                const speechPanel = document.getElementById('speech-feedback-panel');
                if (speechPanel) {
                    speechPanel.style.display = 'none';
                }
            }, 2000);

            // Hide recording indicator
            const recIndicator = document.getElementById('recording-indicator');
            if (recIndicator) {
                recIndicator.style.display = 'none';
            }

            // Hide recording status
            const statusBar = document.getElementById('recording-status-bar');
            if (statusBar) {
                statusBar.style.display = 'none';
            }

            this.updateStatus('Analyzing...');

            // Play sound effect
            if (window.soundManager) {
                window.soundManager.playClick();
            }
        }
    }

    playRecording() {
        if (this.playbackEl.src) {
            this.playbackEl.play();
            this.updateStatus('Playing recording...');
        }
    }

    getCurrentWords() {
        // Get the currently displayed words from the reading app
        if (typeof words !== 'undefined') {
            // Get recent words based on current position
            const currentPositionEl = document.getElementById('current-position');
            const currentIndex = Math.min(parseInt(currentPositionEl?.textContent || 0), words.length);
            const start = Math.max(0, currentIndex - 10);
            const end = Math.min(words.length, currentIndex + 20);
            return words.slice(start, end);
        }
        return [];
    }

    syncWordsWithSpeech(recognizedText) {
        // ONE WORD AT A TIME - only match the current displayed word
        if (!recognizedText || typeof words === 'undefined') return;

        // Prevent multiple rapid advances
        if (this.isAdvancing) return;

        const currentPositionEl = document.getElementById('current-position');
        const currentIndex = parseInt(currentPositionEl?.textContent || 0);
        const wordEl = document.getElementById('word');
        const currentWord = wordEl?.textContent?.toLowerCase().replace(/[.,!?;:]/g, '').trim();

        if (!currentWord) return;

        // Get ONLY the last recognized word (not combining multiple)
        const recognizedWords = recognizedText.toLowerCase().trim().split(/\s+/).filter(w => w);
        if (recognizedWords.length === 0) return;

        // Only check the most recent single word
        const lastRecognizedWord = recognizedWords[recognizedWords.length - 1].replace(/[.,!?;:]/g, '');

        // Check if the CURRENT word matches
        if (currentWord === lastRecognizedWord || this.fuzzyMatch(currentWord, lastRecognizedWord)) {
            this.showWordMatch(true);

            // Mark word as mastered and remove from practice list
            if (typeof window.markWordMastered === 'function') {
                window.markWordMastered(currentWord);
            }

            // Mark as advancing to prevent double-triggers
            this.isAdvancing = true;

            // Track words since last reset (for preventing degradation)
            this.wordsSinceReset++;

            // Reset speech recognition to clear buffer (prevents word mixing)
            if (this.recognition) {
                this.recognition.stop();
            }

            // Play success sound
            if (window.soundManager) {
                window.soundManager.playCorrect();
            }

            // Advance to next word after a brief pause
            setTimeout(() => {
                if (currentIndex < words.length - 1) {
                    this.updateReadingPosition(currentIndex + 1);
                }

                // Restart speech recognition with fresh buffer
                // Do a full reset every N words to prevent degradation
                setTimeout(() => {
                    if (this.isRecording && this.recognition) {
                        this.recognizedText = '';

                        // Periodic full reset to prevent audio degradation
                        if (this.wordsSinceReset >= this.maxWordsBeforeReset) {
                            console.log('Performing periodic recognition reset to maintain audio quality');
                            this.wordsSinceReset = 0;
                            // Recreate recognition instance for fresh state
                            this.refreshRecognition();
                        } else {
                            try {
                                this.recognition.start();
                            } catch (e) {
                                // Recognition might already be running
                            }
                        }
                    }
                    this.isAdvancing = false;
                }, 200);
            }, 400);
        } else {
            // No match yet - show waiting indicator
            this.showWordMatch(false);

            // Track mispronounced word if a clear word was detected that doesn't match
            if (lastRecognizedWord && lastRecognizedWord.length >= 2 && currentWord !== lastRecognizedWord) {
                this.trackMispronunciation(currentWord, lastRecognizedWord);
            }
        }
    }

    // Refresh the recognition instance to prevent degradation after many words
    refreshRecognition() {
        if (this.recognition) {
            try {
                this.recognition.stop();
            } catch (e) {}
        }

        // Recreate recognition instance
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = true;
            this.recognition.interimResults = true;
            this.recognition.lang = 'en-US';

            this.recognition.onresult = (event) => {
                if (this.isAdvancing) return;

                let currentTranscript = '';
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    currentTranscript = event.results[i][0].transcript;
                }
                this.recognizedText = currentTranscript.trim();

                const speechPanel = document.getElementById('live-speech-text');
                if (speechPanel && this.recognizedText) {
                    speechPanel.textContent = this.recognizedText;
                }

                if (this.recognizedText) {
                    this.syncWordsWithSpeech(this.recognizedText);
                }
            };

            this.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
            };

            // Start the fresh recognition
            try {
                this.recognition.start();
            } catch (e) {
                console.error('Failed to start refreshed recognition:', e);
            }
        }
    }

    // Track mispronounced words and save to backend
    trackMispronunciation(expectedWord, actualWord) {
        // Don't track if already tracking this pair recently (debounce)
        const trackingKey = `${expectedWord}-${actualWord}`;
        if (this.lastMistakeTracked === trackingKey) return;
        this.lastMistakeTracked = trackingKey;

        // Clear the tracking key after a delay
        setTimeout(() => {
            if (this.lastMistakeTracked === trackingKey) {
                this.lastMistakeTracked = null;
            }
        }, 2000);

        console.log(`Mispronunciation detected: expected "${expectedWord}", heard "${actualWord}"`);

        // Save to backend
        this.saveWordMistake(expectedWord, actualWord, 'mispronounced');
    }

    // Save word mistake to backend
    async saveWordMistake(expectedWord, actualWord, mistakeType) {
        try {
            // Get current user info from cookie or session
            const userDisplay = document.getElementById('current-user-display');
            const username = userDisplay?.textContent || 'Guest';

            const response = await fetch(`${this.apiBase}/save_word_mistake`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    expected_word: expectedWord,
                    actual_word: actualWord,
                    mistake_type: mistakeType,
                    username: username,
                    category: this.getCurrentCategory()
                })
            });

            if (!response.ok) {
                console.error('Failed to save word mistake');
            } else {
                console.log(`Word mistake saved: ${expectedWord} -> ${actualWord} (${mistakeType})`);
            }
        } catch (error) {
            console.error('Error saving word mistake:', error);
        }
    }

    // Get current word category if available
    getCurrentCategory() {
        // Try to get from active category button
        const activeCategory = document.querySelector('.category-btn.active');
        if (activeCategory) {
            return activeCategory.dataset.category || '';
        }
        return '';
    }

    // Check if two words are homophones (sound the same)
    areHomophones(word1, word2) {
        if (!word1 || !word2) return false;

        const w1 = word1.toLowerCase().trim();
        const w2 = word2.toLowerCase().trim();

        // Direct match
        if (w1 === w2) return true;

        // Check homophone dictionary
        const homophones1 = this.homophones[w1];
        if (homophones1 && homophones1.includes(w2)) {
            return true;
        }

        const homophones2 = this.homophones[w2];
        if (homophones2 && homophones2.includes(w1)) {
            return true;
        }

        return false;
    }

    // Check if two words are near-matches (commonly confused by speech recognition)
    areNearMatches(word1, word2) {
        if (!word1 || !word2) return false;

        const w1 = word1.toLowerCase().trim();
        const w2 = word2.toLowerCase().trim();

        // Direct match
        if (w1 === w2) return true;

        // Check near-match dictionary
        const nearMatches1 = this.nearMatches[w1];
        if (nearMatches1 && nearMatches1.includes(w2)) {
            console.log(`Near-match found: "${w1}" is close to "${w2}"`);
            return true;
        }

        const nearMatches2 = this.nearMatches[w2];
        if (nearMatches2 && nearMatches2.includes(w1)) {
            console.log(`Near-match found: "${w2}" is close to "${w1}"`);
            return true;
        }

        return false;
    }

    // Check if two words are equivalent numbers (e.g., "thirteen" == "13")
    areNumbersEquivalent(word1, word2) {
        if (!word1 || !word2) return false;

        const w1 = word1.toLowerCase().trim();
        const w2 = word2.toLowerCase().trim();

        // Direct match
        if (w1 === w2) return true;

        // Check if w1 is a number word and w2 is its digit equivalent
        if (this.numberWords[w1] === w2) {
            return true;
        }

        // Check if w2 is a number word and w1 is its digit equivalent
        if (this.numberWords[w2] === w1) {
            return true;
        }

        // Check if both map to the same digit
        const digit1 = this.numberWords[w1];
        const digit2 = this.numberWords[w2];
        if (digit1 && digit2 && digit1 === digit2) {
            return true;
        }

        // Check if w1 is a digit and w2 is one of its word equivalents
        if (this.digitsToWords[w1] && this.digitsToWords[w1].includes(w2)) {
            return true;
        }

        // Check if w2 is a digit and w1 is one of its word equivalents
        if (this.digitsToWords[w2] && this.digitsToWords[w2].includes(w1)) {
            return true;
        }

        return false;
    }

    fuzzyMatch(word1, word2) {
        // Improved fuzzy matching with Levenshtein distance, homophone support, near-matches, AND number matching
        if (!word1 || !word2) return false;
        if (word1 === word2) return true;

        // Check if they are homophones (sound the same) - this is key for reading tests!
        if (this.areHomophones(word1, word2)) {
            console.log(`Homophone match: "${word1}" sounds like "${word2}"`);
            return true;
        }

        // Check if they are near-matches (commonly confused by speech recognition, like tube/tub)
        if (this.areNearMatches(word1, word2)) {
            console.log(`Near-match accepted: "${word1}" is close enough to "${word2}"`);
            return true;
        }

        // Check if they are equivalent numbers (e.g., "thirteen" matches "13")
        if (this.areNumbersEquivalent(word1, word2)) {
            console.log(`Number match: "${word1}" is equivalent to "${word2}"`);
            return true;
        }

        // Quick check for very different lengths (skip Levenshtein for obviously different words)
        if (Math.abs(word1.length - word2.length) > 3) return false;

        // Calculate Levenshtein distance for spelling variations
        const matrix = [];
        for (let i = 0; i <= word2.length; i++) {
            matrix[i] = [i];
        }
        for (let j = 0; j <= word1.length; j++) {
            matrix[0][j] = j;
        }

        for (let i = 1; i <= word2.length; i++) {
            for (let j = 1; j <= word1.length; j++) {
                if (word2.charAt(i - 1) === word1.charAt(j - 1)) {
                    matrix[i][j] = matrix[i - 1][j - 1];
                } else {
                    matrix[i][j] = Math.min(
                        matrix[i - 1][j - 1] + 1, // substitution
                        matrix[i][j - 1] + 1,     // insertion
                        matrix[i - 1][j] + 1      // deletion
                    );
                }
            }
        }

        const distance = matrix[word2.length][word1.length];
        const maxLength = Math.max(word1.length, word2.length);

        // Allow up to 30% difference
        return distance <= maxLength * 0.3;
    }

    showWordMatch(isCorrect) {
        const indicator = document.getElementById('accuracy-indicator');
        const status = document.getElementById('word-match-status');

        if (indicator) {
            if (isCorrect) {
                indicator.textContent = '✅';
                indicator.style.color = '#28a745';
            } else {
                indicator.textContent = '❌';
                indicator.style.color = '#dc3545';
            }

            // Reset after animation
            setTimeout(() => {
                indicator.textContent = '⭕';
                indicator.style.color = '#6c757d';
            }, 1000);
        }

        if (status) {
            status.textContent = isCorrect ? '✓ Match!' : '✗ Keep trying';
            status.style.color = isCorrect ? '#28a745' : '#ffc107';
        }
    }

    updateReadingPosition(newIndex) {
        // Update the reading position to sync with speech
        const currentPositionEl = document.getElementById('current-position');
        const wordEl = document.getElementById('word');
        const progressBar = document.getElementById('progress-bar');

        // Check if we've reached the end of the word list
        if (newIndex >= words.length) {
            // Session complete!
            this.showSessionComplete();
            return;
        }

        if (currentPositionEl && newIndex < words.length) {
            currentPositionEl.textContent = newIndex;

            // Update displayed word - NO ANIMATION to avoid flash
            if (wordEl && words[newIndex]) {
                wordEl.textContent = words[newIndex];
            }

            // Update progress bar smoothly
            if (progressBar && words.length > 0) {
                const percentage = (newIndex / words.length) * 100;
                progressBar.style.width = percentage + '%';
            }
        }

        // Clear the speech feedback text for fresh start
        const speechPanel = document.getElementById('live-speech-text');
        if (speechPanel) {
            speechPanel.textContent = '...';
        }
    }

    showSessionComplete() {
        const wordEl = document.getElementById('word');
        if (wordEl) {
            wordEl.textContent = '🎉 Great job! Session complete!';
            wordEl.style.color = '#28a745';
        }

        // Play achievement sound
        if (window.soundManager) {
            window.soundManager.playAchievement();
        }

        // Stop recording automatically
        if (this.isRecording) {
            setTimeout(() => this.stopRecording(), 1000);
        }

        // Update status
        this.updateStatus('Session complete! You read all the words.');
    }

    // Skip current word - called when user manually skips a difficult word
    skipCurrentWord() {
        if (!this.isRecording) return;

        // Prevent advancing state conflicts
        this.isAdvancing = true;

        // Get the current word being skipped for tracking
        const wordEl = document.getElementById('word');
        const skippedWord = wordEl?.textContent?.toLowerCase().replace(/[.,!?;:]/g, '').trim();

        // Save skipped word to backend
        if (skippedWord) {
            this.saveWordMistake(skippedWord, null, 'skipped');
        }

        // Reset speech recognition to clear any partial matches
        if (this.recognition) {
            try {
                this.recognition.stop();
            } catch (e) {
                // Recognition might not be running
            }
        }

        // Clear the recognized text buffer
        this.recognizedText = '';

        // Clear the speech feedback display
        const speechPanel = document.getElementById('live-speech-text');
        if (speechPanel) {
            speechPanel.textContent = '...';
        }

        // Show skip indicator
        const indicator = document.getElementById('accuracy-indicator');
        if (indicator) {
            indicator.textContent = '⏭';
            indicator.style.color = '#fd7e14';
            setTimeout(() => {
                indicator.textContent = '⭕';
                indicator.style.color = '#6c757d';
            }, 1000);
        }

        // Track words since last reset
        this.wordsSinceReset++;

        // Restart recognition after a brief pause
        setTimeout(() => {
            if (this.isRecording && this.recognition) {
                // Periodic full reset to prevent audio degradation
                if (this.wordsSinceReset >= this.maxWordsBeforeReset) {
                    console.log('Performing periodic recognition reset on skip');
                    this.wordsSinceReset = 0;
                    this.refreshRecognition();
                } else {
                    try {
                        this.recognition.start();
                    } catch (e) {
                        // Recognition might already be running
                    }
                }
            }
            this.isAdvancing = false;
        }, 300);
    }

    analyzeRecording() {
        // Compare recognized text with expected words
        const expectedText = this.expectedWords.join(' ').toLowerCase();
        const recognizedLower = this.recognizedText.toLowerCase().trim();

        // Calculate accuracy
        const accuracy = this.calculateAccuracy(expectedText, recognizedLower);

        // Generate feedback
        this.showFeedback(accuracy, expectedText, recognizedLower);

        // Save results to database
        this.saveResults(accuracy, this.recognizedText);
    }

    calculateAccuracy(expected, recognized) {
        if (!expected || !recognized) return 0;

        const expectedWords = expected.split(' ').filter(w => w);
        const recognizedWords = recognized.split(' ').filter(w => w);

        let matches = 0;
        expectedWords.forEach(expectedWord => {
            // Check for exact match first
            if (recognizedWords.includes(expectedWord)) {
                matches++;
            } else {
                // Check for homophone match - words that sound the same count as correct!
                let matched = false;
                for (const recognizedWord of recognizedWords) {
                    if (this.areHomophones(expectedWord, recognizedWord)) {
                        matches++;
                        matched = true;
                        break;
                    }
                    // Check for number equivalent match (e.g., "thirteen" matches "13")
                    if (this.areNumbersEquivalent(expectedWord, recognizedWord)) {
                        matches++;
                        matched = true;
                        break;
                    }
                }
            }
        });

        return Math.round((matches / expectedWords.length) * 100);
    }

    showFeedback(accuracy, expected, recognized) {
        // If feedback element doesn't exist, create it dynamically
        let feedbackEl = document.getElementById('recording-feedback');
        if (!feedbackEl) {
            feedbackEl = document.createElement('div');
            feedbackEl.id = 'recording-feedback';
            feedbackEl.className = 'recording-feedback';
            feedbackEl.style.cssText = `
                background: white;
                border: 2px solid #ddd;
                border-radius: 8px;
                padding: 20px;
                margin: 20px 0;
                display: none;
            `;
            feedbackEl.innerHTML = `
                <h4>Recording Feedback</h4>
                <div id="accuracy-score" style="font-size: 24px; margin: 10px 0;"></div>
                <div id="words-analysis"></div>
                <div id="pronunciation-tips"></div>
            `;

            // Insert after recording controls
            const recordingSection = document.querySelector('.recording-section');
            if (recordingSection) {
                recordingSection.appendChild(feedbackEl);
            } else {
                // Fallback: insert after main content
                const mainContent = document.querySelector('.main-content');
                if (mainContent) {
                    mainContent.appendChild(feedbackEl);
                }
            }
        }

        const scoreEl = document.getElementById('accuracy-score');
        const wordsEl = document.getElementById('words-analysis');
        const tipsEl = document.getElementById('pronunciation-tips');

        if (!scoreEl || !wordsEl || !tipsEl) {
            console.error('Feedback elements not found');
            return;
        }

        // Show feedback section
        feedbackEl.style.display = 'block';

        // Display score with color coding
        let scoreColor = '#28a745'; // green
        let scoreEmoji = '🎉';
        if (accuracy < 50) {
            scoreColor = '#dc3545'; // red
            scoreEmoji = '😢';
        } else if (accuracy < 80) {
            scoreColor = '#ffc107'; // yellow
            scoreEmoji = '😊';
        }

        scoreEl.innerHTML = `
            <span style="color: ${scoreColor}">${accuracy}%</span>
            <span style="font-size: 48px; margin-left: 10px;">${scoreEmoji}</span>
        `;

        // Word-by-word analysis with homophone and number support
        const expectedWords = expected.split(' ').filter(w => w);
        const recognizedWords = recognized.split(' ').filter(w => w);

        let analysisHTML = '<h5>Word Analysis:</h5><div style="display: flex; flex-wrap: wrap; gap: 10px;">';
        expectedWords.forEach(word => {
            let isCorrect = recognizedWords.includes(word);
            let isHomophone = false;
            let isNumberMatch = false;
            let matchedWord = '';

            // Check for homophone match if not exact match
            if (!isCorrect) {
                for (const recognizedWord of recognizedWords) {
                    if (this.areHomophones(word, recognizedWord)) {
                        isCorrect = true;
                        isHomophone = true;
                        matchedWord = recognizedWord;
                        break;
                    }
                    // Check for number equivalent match
                    if (this.areNumbersEquivalent(word, recognizedWord)) {
                        isCorrect = true;
                        isNumberMatch = true;
                        matchedWord = recognizedWord;
                        break;
                    }
                }
            }

            const bgColor = isCorrect ? '#d4edda' : '#f8d7da';
            const textColor = isCorrect ? '#155724' : '#721c24';
            const icon = isCorrect ? '✓' : '✗';
            let matchNote = '';
            let matchTitle = '';
            if (isHomophone) {
                matchNote = ` (heard: "${matchedWord}")`;
                matchTitle = 'Homophone match - sounds the same!';
            } else if (isNumberMatch) {
                matchNote = ` (heard: "${matchedWord}")`;
                matchTitle = 'Number match - same number, different form!';
            }

            analysisHTML += `
                <span style="padding: 5px 10px; background: ${bgColor}; color: ${textColor}; border-radius: 5px;" title="${matchTitle}">
                    ${word}${matchNote} ${icon}
                </span>
            `;
        });
        analysisHTML += '</div>';

        if (recognized && recognized !== expected) {
            analysisHTML += `<p style="margin-top: 15px;"><strong>You said:</strong> "${recognized}"</p>`;
        }

        wordsEl.innerHTML = analysisHTML;

        // Pronunciation tips
        let tips = '<h5>💡 Tips:</h5><ul style="margin: 0; padding-left: 20px;">';
        if (accuracy < 100) {
            tips += '<li>Speak clearly and at a moderate pace</li>';
            tips += '<li>Make sure you\'re in a quiet environment</li>';
            tips += '<li>Try pronouncing each word distinctly</li>';
        }
        if (accuracy >= 80) {
            tips += '<li>Great job! Keep practicing to maintain your skills</li>';
        }
        tips += '</ul>';

        tipsEl.innerHTML = tips;

        // Play appropriate sound effect
        if (window.soundManager) {
            if (accuracy >= 80) {
                window.soundManager.playCorrect();
            } else {
                window.soundManager.playIncorrect();
            }
        }
    }

    async saveResults(accuracy, recognizedText) {
        try {
            const response = await fetch(`${this.apiBase}/save_reading_result`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    expected_words: this.expectedWords,
                    recognized_text: recognizedText,
                    accuracy: accuracy,
                    timestamp: new Date().toISOString()
                })
            });

            if (!response.ok) {
                console.error('Failed to save reading results');
            } else {
                // Refresh statistics after saving
                if (typeof loadReadingStats === 'function') {
                    setTimeout(() => loadReadingStats(), 500);
                }
            }
        } catch (error) {
            console.error('Error saving results:', error);
        }
    }

    updateStatus(message) {
        if (this.statusEl) {
            this.statusEl.textContent = message;
        }
    }

    startVisualizer() {
        if (!this.analyser || !this.visualizerCtx) return;

        const bufferLength = this.analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        const draw = () => {
            if (!this.isRecording) return;

            requestAnimationFrame(draw);

            this.analyser.getByteFrequencyData(dataArray);

            const canvas = this.visualizerCanvas;
            const ctx = this.visualizerCtx;
            const width = canvas.width = canvas.offsetWidth;
            const height = canvas.height = canvas.offsetHeight;

            ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
            ctx.fillRect(0, 0, width, height);

            const barWidth = (width / bufferLength) * 2.5;
            let barHeight;
            let x = 0;

            for (let i = 0; i < bufferLength; i++) {
                barHeight = (dataArray[i] / 255) * height;

                const r = 255;
                const g = 255;
                const b = 255;

                ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.8)`;
                ctx.fillRect(x, height - barHeight, barWidth, barHeight);

                x += barWidth + 1;
            }
        };

        draw();
    }

    stopVisualizer() {
        // Clear the canvas
        if (this.visualizerCtx && this.visualizerCanvas) {
            this.visualizerCtx.clearRect(0, 0, this.visualizerCanvas.width, this.visualizerCanvas.height);
        }

        // Close audio context
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
    }

    // Microphone Test Methods
    showMicTest() {
        if (this.micTestSection) {
            this.micTestSection.style.display = 'block';
            // Play sound effect
            if (window.soundManager) {
                window.soundManager.playClick();
            }
        }
    }

    closeMicTest() {
        if (this.micTestSection) {
            this.micTestSection.style.display = 'none';
            this.stopMicTest();
        }
    }

    async startMicTest() {
        try {
            this.micTestStatus.textContent = '🎤 Requesting microphone access...';

            // Get audio stream
            this.testStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            this.micTestStatus.textContent = '✅ Microphone connected! Speak now...';

            // Show/hide buttons
            this.startTestBtn.style.display = 'none';
            this.stopTestBtn.style.display = 'inline-block';

            // Setup audio analysis for volume meter
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const analyser = audioContext.createAnalyser();
            const microphone = audioContext.createMediaStreamSource(this.testStream);
            const scriptProcessor = audioContext.createScriptProcessor(2048, 1, 1);

            analyser.smoothingTimeConstant = 0.8;
            analyser.fftSize = 1024;

            microphone.connect(analyser);
            analyser.connect(scriptProcessor);
            scriptProcessor.connect(audioContext.destination);

            scriptProcessor.onaudioprocess = () => {
                if (!this.isTestingMic) return;

                const array = new Uint8Array(analyser.frequencyBinCount);
                analyser.getByteFrequencyData(array);
                const values = array.reduce((a, b) => a + b, 0);
                const average = values / array.length;
                const volume = Math.min(100, Math.round(average * 1.5));

                // Update volume meter
                if (this.volumeMeter) {
                    this.volumeMeter.style.width = volume + '%';
                }
            };

            this.isTestingMic = true;

            // Setup speech recognition for test
            if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                this.testRecognition = new SpeechRecognition();
                this.testRecognition.continuous = true;
                this.testRecognition.interimResults = true;
                this.testRecognition.lang = 'en-US';

                this.testRecognition.onresult = (event) => {
                    let transcript = '';
                    for (let i = event.resultIndex; i < event.results.length; i++) {
                        transcript += event.results[i][0].transcript;
                    }
                    if (transcript) {
                        this.detectedSpeechEl.textContent = transcript;
                        this.detectedSpeechEl.style.color = '#28a745';
                    }
                };

                this.testRecognition.onerror = (event) => {
                    this.detectedSpeechEl.textContent = `Speech recognition error: ${event.error}`;
                    this.detectedSpeechEl.style.color = '#dc3545';
                };

                this.testRecognition.start();
            }

            // Play success sound
            if (window.soundManager) {
                window.soundManager.playCorrect();
            }

        } catch (error) {
            console.error('Mic test error:', error);
            let errorMessage = '❌ Microphone test failed: ';

            if (error.name === 'NotAllowedError') {
                errorMessage += 'Permission denied. Please allow microphone access.';
            } else if (error.name === 'NotFoundError') {
                errorMessage += 'No microphone found.';
            } else if (error.name === 'NotReadableError') {
                errorMessage += 'Microphone is in use by another app.';
            } else {
                errorMessage += error.message;
            }

            this.micTestStatus.textContent = errorMessage;
            this.micTestStatus.style.color = '#dc3545';

            // Play error sound
            if (window.soundManager) {
                window.soundManager.playIncorrect();
            }
        }
    }

    stopMicTest() {
        this.isTestingMic = false;

        // Stop all tracks
        if (this.testStream) {
            this.testStream.getTracks().forEach(track => track.stop());
            this.testStream = null;
        }

        // Stop speech recognition
        if (this.testRecognition) {
            this.testRecognition.stop();
            this.testRecognition = null;
        }

        // Reset UI
        this.startTestBtn.style.display = 'inline-block';
        this.stopTestBtn.style.display = 'none';
        this.volumeMeter.style.width = '0%';
        this.micTestStatus.textContent = 'Click "Start Test" and speak into your microphone...';
        this.detectedSpeechEl.textContent = 'Waiting for speech...';
        this.detectedSpeechEl.style.color = '';
    }
}

// Function to fetch and display reading statistics
async function loadReadingStats() {
    try {
        // Detect API base path
        const apiBase = window.location.pathname.startsWith('/reading') ? '/reading/api' : '/api';
        const response = await fetch(`${apiBase}/reading_stats`);
        if (!response.ok) return;

        const stats = await response.json();

        // Update main statistics
        const totalSessionsEl = document.getElementById('total-sessions');
        const avgAccuracyEl = document.getElementById('avg-accuracy');
        const wordsMasteredEl = document.getElementById('words-mastered');

        if (totalSessionsEl) totalSessionsEl.textContent = stats.total_sessions || 0;
        if (avgAccuracyEl) avgAccuracyEl.textContent = `${stats.avg_accuracy || 0}%`;
        if (wordsMasteredEl) wordsMasteredEl.textContent = stats.mastered_words?.length || 0;

        // Update challenging words list
        const challengingListEl = document.getElementById('challenging-words-list');
        if (challengingListEl && stats.challenging_words?.length > 0) {
            challengingListEl.innerHTML = stats.challenging_words.map(word => `
                <div style="padding: 5px 0; border-bottom: 1px solid #eee;">
                    <span style="font-weight: bold;">${word.word}</span>
                    <span style="color: #dc3545; float: right;">${word.accuracy_rate || 0}%</span>
                </div>
            `).join('');
        }

        // Update mastered words list
        const masteredListEl = document.getElementById('mastered-words-list');
        if (masteredListEl && stats.mastered_words?.length > 0) {
            masteredListEl.innerHTML = stats.mastered_words.map(word => `
                <div style="padding: 5px 0; border-bottom: 1px solid #eee;">
                    <span style="font-weight: bold;">${word.word}</span>
                    <span style="color: #28a745; float: right;">✓ ${word.correct_count}</span>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading reading stats:', error);
    }
}

// Function to integrate recording with reading session
function setupReadingRecordingIntegration() {
    // Listen for reading session start/stop
    const playBtn = document.getElementById('play-btn');
    const pauseBtn = document.getElementById('pause-btn');

    if (playBtn && window.audioRecorder) {
        const originalPlayClick = playBtn.onclick;
        playBtn.onclick = function() {
            // Call original play function
            if (originalPlayClick) originalPlayClick.call(this);

            // Auto-start recording if enabled and not already recording
            if (window.audioRecorder.autoStartEnabled && !window.audioRecorder.isRecording) {
                setTimeout(() => {
                    window.audioRecorder.startRecording(true);
                }, 500); // Small delay to let reading start
            }
        };
    }

    if (pauseBtn && window.audioRecorder) {
        const originalPauseClick = pauseBtn.onclick;
        pauseBtn.onclick = function() {
            // Call original pause function
            if (originalPauseClick) originalPauseClick.call(this);

            // Stop recording when pausing reading
            if (window.audioRecorder.isRecording) {
                window.audioRecorder.stopRecording();
            }
        };
    }
}

// Initialize recorder when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
    const mobileNotice = document.getElementById('mobile-notice');
    const iosIncompatible = document.getElementById('ios-incompatible');

    // Check iOS version and MediaRecorder support
    if (isIOS) {
        // Check if MediaRecorder is available
        if (typeof MediaRecorder === 'undefined') {
            // MediaRecorder not supported - old iOS version
            if (iosIncompatible) {
                iosIncompatible.style.display = 'block';
            }
            // Disable record button
            const recordBtn = document.getElementById('record-btn');
            if (recordBtn) {
                recordBtn.disabled = true;
                recordBtn.textContent = '🔴 Not Supported on This Device';
                recordBtn.style.opacity = '0.5';
            }
        } else if (mobileNotice) {
            // Show general iOS notice
            mobileNotice.style.display = 'block';
        }
    }

    if (document.getElementById('record-btn') && typeof MediaRecorder !== 'undefined') {
        window.audioRecorder = new AudioRecorder();
        // Set up integration with reading session
        setTimeout(() => {
            setupReadingRecordingIntegration();
        }, 100);
    }

    // Load statistics on page load
    loadReadingStats();

    // Add refresh button handler
    const refreshBtn = document.getElementById('refresh-stats-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            loadReadingStats();
            refreshBtn.textContent = '✓ Refreshed!';
            setTimeout(() => {
                refreshBtn.textContent = '🔄 Refresh Statistics';
            }, 2000);
        });
    }
});
