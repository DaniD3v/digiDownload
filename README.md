# digiDownload
API to download books from [http://digi4school.at](http://digi4school.at)  
`pip install digiDownload`

# Console Menu
built-in cli menu:  
`python -m digiDownload`

```
Select the books you want to download:

1: [ ] Mathematik mit technischen Anwendungen                        
2: [x] das deutschbuch.                                                         
R: Register new book.                                                                    
F: Finish selection.
```

# Async
This library makes extensive use of asyncio, allowing your code to be more efficient.

# Future plans
Add synchronous Book/Session class wrappers to make this more accessible for beginners.
Allow for downloading all the volumes of an E-Book instead of simply using the first one.

# Compatibility
Due to the inconsistency of digi4school this library only supports a limited set of books.
Because I can only test the library with the books I have access to, I don't even know which books will work.

- Books hosted directly on digi4school.at or hpthek.at will likely work
- there is limited compatibility with books that have multiple volumes
