# Paraphrasing rules

The notes pages must be **paraphrased educational summaries**, not reproductions of the source. This is how you keep the output legally safe (fair use for personal study), pedagogically useful (condensed, not bloated), and respectful to the source author (you point users back to the book for depth).

## What to cut

- Filler prose: "in this chapter we will explore...", "as we shall see", "let us now turn our attention to"
- Repeated explanations the author included for emphasis
- Motivational asides and pep talks
- Long anecdotes that don't carry technical content
- Redundant summaries at the end of sections
- "Why this matters" preambles unless they contain genuine technical insight
- **Meta-narration about the chapter or book.** This is the subtler failure mode. Even after the obvious filler is gone, intros tend to drift into describing the document instead of teaching the topic. Cut:
  - "This chapter sets up / walks through / covers / introduces..."
  - "By the end of this chapter you will..."
  - "Everything later in the book builds on this", "we'll return to this in chapter N"
  - Sentences whose grammatical subject is *the chapter*, *the book*, or *we* (as in the author-and-reader "we")
  - Lists of upcoming section headings stitched into a sentence ("...covers the syntactic core: variables, arithmetic, arrays, streams...")

  If a sentence is *about the text* rather than *about the subject*, rewrite or delete it. The reader can see the section headings as they scroll; they don't need them announced in prose.

## What to keep verbatim

These are the technical bones of the chapter. Paraphrasing them introduces bugs.

- **Code blocks**: every line, every comment, every variable name
- **Command syntax**: `nmap -sV -sC -oA scan target.com` stays exactly as written
- **Error messages**: "Connection reset by peer" stays as "Connection reset by peer"
- **API names, function names, method names**: `socket.SOCK_STREAM`, `WMI Win32_Process`
- **File paths and registry keys**: `C:\Windows\System32\config\SAM`, `HKLM\SOFTWARE\Microsoft\...`
- **Configuration values**: port numbers, magic bytes, default values
- **Version numbers and version-specific behaviour**: "Python 3.10 introduced...", "Server 2019 changed..."
- **Specifications**: RFC numbers, CVE numbers, CWE IDs, MITRE ATT&CK technique IDs
- **Acronyms on first use**: DLL (Dynamic Link Library), TGT (Ticket Granting Ticket)

## What to paraphrase tightly

These are the parts where you condense.

- **Conceptual explanations**: what something is, why it works the way it does
- **Process descriptions**: walk-throughs of how a thing happens, in your own words
- **Definitions of terms**: the source's definition is copyrighted; your distilled version is fine
- **"Why this matters" reasoning**: extract the core point, drop the framing

## What to preserve fully

- **Worked examples**: the example itself, with its inputs and outputs, since the user needs to see the same thing the book showed
- **Step-by-step procedures**: each step matters; condensing risks dropping a step
- **Diagrams and tables**: convert to clear textual form or markdown tables, but include all the information

## Length target

Aim for **40-60% of the original chapter length** for prose-heavy chapters. Code-heavy chapters might be longer (because code stays verbatim). If you're hitting 80%+ of the original length, you're not paraphrasing, you're transcribing.

If you're below 30%, you've lost detail. Go back and check.

## Worked example

### Source (verbatim, hypothetical)

> When we want to send data over the network, we need to think carefully about how that data is going to be packaged. The TCP protocol, which stands for Transmission Control Protocol, is what we call a connection-oriented protocol. This means that before any actual data flows between two endpoints, those endpoints must establish a connection through a process called the three-way handshake. The three-way handshake works like this: the client sends a SYN packet, which is short for synchronize. The server responds with a SYN-ACK packet, which acknowledges the client's request and sends its own synchronize. Finally, the client responds with an ACK packet, completing the handshake. Once this is done, data can flow reliably between the two endpoints, with TCP ensuring that packets arrive in order and that lost packets are retransmitted.

### Bad paraphrase (still too close to source)

> When sending data over a network, we must consider how it's packaged. TCP (Transmission Control Protocol) is a connection-oriented protocol, meaning endpoints establish a connection via a three-way handshake before any data flows. The handshake: client sends SYN, server replies SYN-ACK, client replies ACK. Then data flows reliably with ordering and retransmission.

This is closer but still mirrors the source's structure too closely.

### Good paraphrase (actually rewritten)

> TCP is connection-oriented: endpoints negotiate a connection before exchanging data. The negotiation is the three-way handshake.
>
> 1. Client sends `SYN`.
> 2. Server replies with `SYN-ACK`.
> 3. Client replies with `ACK`.
>
> Once established, TCP guarantees in-order delivery and retransmits lost segments.

This is shorter, restructured, but loses no technical detail. The handshake mechanics are preserved exactly because they're the technical content; the explanatory framing is rewritten.

## Worked example: chapter intros

Intros are the place meta-narration creeps back in even after the filler-cutting rules have been applied. The model strips "in this chapter we will explore" and then produces the same stance with different words. Watch for it.

### Bad intro (narrates the chapter)

> Bash is the command interpreter pentesters reach for to automate Linux tasks. This chapter sets up a working bash environment, walks through the building blocks of a script (shebang, comments, execution, debugging), and covers the syntactic core: variables, arithmetic, arrays, streams, operators, redirection, positional arguments, input prompting, and exit codes. Everything later in the book builds on these pieces.

The first sentence is fine — its subject is *Bash*. The rest collapses into back-cover blurb: the subject becomes *this chapter*, the verbs are document verbs (*sets up*, *walks through*, *covers*), and the third sentence is pure scaffolding. The list of topics is just the upcoming section headings reformatted as prose, which is wasted words — the reader is about to see them anyway.

### Good intro (teaches the subject)

> Bash is the default command interpreter on most Linux systems, and the language pentesters reach for when they need to glue tools together, automate a foothold, or script a repeatable check across hosts. A bash script is a plain text file the shell reads top to bottom: each line is either a command, a control structure, or a variable manipulation. Before any of that runs, the shell needs to know two things — what interpreter to use (the shebang) and that the file is executable.

Same opening sentence. After that, the subject of every sentence is *Bash*, *a script*, or *the shell* — never *the chapter*. There's no preview of what's coming; instead the intro starts teaching, and the next subsection picks up naturally with the shebang. The reader sees structure by scrolling, not by being told.

### How to write intros this way

- Open by saying what the topic *is* and where it sits in the world, not what the chapter will do with it.
- If you want to motivate a topic, do it concretely (an example of when you'd reach for it), not by promising future coverage.
- End the intro on a sentence that hands off into the first subsection's content — not on a roadmap of the chapter.
- If you catch yourself writing "this chapter", "the book", or "we will", stop and rewrite with the topic as the subject.

## What if the source is very dense and there's nothing to cut?

Then keep it. The 40-60% target is for prose-heavy content. A chapter that's already lean (e.g. a reference chapter listing every flag of every command) might end up at 80% of the original because there's no fat to trim. That's fine.

## What if you can't tell whether something is technical content?

Default to keeping it. Losing a detail is worse than being a bit verbose.

## Citation

At the start of each chapter's notes, include a one-line attribution:

> Notes paraphrased from {{BOOK_TITLE}} by {{AUTHOR}}, Chapter {{N}}: {{CHAPTER_TITLE}}. Buy the book to support the author and get the full content.

Always include this. It's good practice, and it pushes users to the source if they want depth the notes deliberately don't provide.
