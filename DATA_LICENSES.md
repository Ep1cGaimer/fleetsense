# Data and asset provenance

NASA C-MAPSS simulated engine trajectories are downloaded from the public PHM dataset mirror named in the supplied plan. Only the run-to-failure training files for the registered subsets are used. The archive and extracted dataset remain outside Git; the downloaded files retain their included dataset documentation. Public availability is not treated as permission to redistribute under the code licence.

Source: https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip

Dataset hashes are recorded independently in the final manifest and `data/raw/SHA256SUMS`. This prototype makes no claim about operational aircraft datasets.

Local Inter and JetBrains Mono fonts are copied, without modification, from the existing Sovereign UI, together with its font licence file. Plotly JavaScript is copied from the resolved Python distribution; its version, hash and upstream licence are documented in `app/ui/vendor/VENDOR.md`.

Submission assets are managed separately by the main implementation and retain their own provenance.
