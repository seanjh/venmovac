# Venmo-Instagram Pairing
The match_instagram module pairs Venmo and Instagram users. The Venmo data is sourced from the venmovac Venmo Public API scraper, stored in MongoDB.

## match_insta.py
This module pairs the Venmo users with Instagram users. The paired user objects are stored in the *venmo_instagram* MongoDB collection.

Before trying to establish any Venmo-Instagram matches, each Venmo user is grouped with a collection of other unique Venmo users they've trasacted with (payment targets). These results are stored in the *user_pairs* collection in MongoDB, based on the data available in the main *trans* collection. Venmo "heavy users" are defined as any users that have >=N unique payment targets, where N is specified by the THRESHOLD argument (defaults to 50).

Given these Venmo users, Instagram users are queried using the full name the heavy Venmo user. Instagram returns up to 3 potential matches. For each of these Instagram results, the full names of the Venmo user's payment targets and the full names of each Instagram user's following users is compared. The heavy Venmo user is paired to the single Instagram user that matches the largest number of following users to its payment target users. If no matches between the Instagram following and Venmo payment target users are found, no Venmo-Instagram match is established.

### CLI interface

    usage: insta_query.py [-h] [-rv] [-t THRESHOLD] tokens [tokens ...]

    positional arguments:
      tokens                Instagram OAuth access tokens

    optional arguments:
      -h, --help            show this help message and exit
      -rv                   Repopulate heavy Venmo users data from Venmo
                            transactions
      -t THRESHOLD, --threshold THRESHOLD
                            Threshold number of unique Venmo users transacted
                            after which some user is considered a "heavy user"
                            (default: 50)

## VenmoTransAndInstagram.ipynb
The VenmoTransAndInstagram IPython notebook compares the activity of a paired Instagram and Venmo user across the 2 services over time.

### Instructions
    ipython notebook VenmoTransAndInstagram.ipynb