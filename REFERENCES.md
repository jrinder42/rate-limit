# References

- Linear Programming
  - https://news.ycombinator.com/item?id=44393998
  - https://vivekn.dev/blog/rate-limit-diophantine
- Async Rate Limiting
  - https://asynciolimiter.readthedocs.io/en/latest/
- Algorithms
  - [Leaky Bucket](https://en.wikipedia.org/wiki/Leaky_bucket)
    - Benefits: Smooth, predictable traffic at a constant rate, discarding the overflow
  - [Token Bucket](https://en.wikipedia.org/wiki/Token_bucket)
    - Benefits: Can be bursty with burst up to a limit, then at an average rate
  - [Fixed Window Counter](https://dev.to/satrobit/rate-limiting-using-the-fixed-window-algorithm-2hgm)
    - Benefits: Simple to implement, but can lead to spikes at the boundaries
  - [Sliding Window Counter](https://medium.com/@avocadi/rate-limiter-sliding-window-counter-7ec08dbe21d6)
    - Benefits: More accurate than fixed window, but more complex
  - [Sliding Window Log](https://rdiachenko.com/posts/arch/rate-limiting/sliding-window-algorithm/)
    - Benefits: Most accurate, but requires more storage and processing