In an ubuntu console...

```console
$ xmllint --noout --schema XML4dbDumps.xsd pmr-mx-2024-11-21.xml
```


```console
$ python pmr_mx_fmt.py https://models.physiomeproject.org/e/
<database>
  <name>Physiome Model Repository</name>
  <description>The main goal of the Physiome Model Repository is to provide a resource for the community to store, retrieve, search, reference, and reuse CellML models.</description>
  <release>12</release>
  <release_date>2020-01-01</release_date>
  <entry_count>620</entry_count>
  <entries>  
    
    <entry id="https://models.physiomeproject.org/e/3fd">
      <name></name>
    </entry>

    <entry id="https://models.physiomeproject.org/e/105">
      <name>A Quantitative Model of Human Jejunal Smooth Muscle Cell Electrophysiology</name>
    </entry>

    <entry id="https://models.physiomeproject.org/e/27d">
      <name>An analysis of deformation-dependent electromechanical coupling in the mouse heart</name>
    </entry>
...
    <entry id="https://models.physiomeproject.org/exposure/01f6a47881da1925315d1d89d3a8d901">
      <name>Zhang, Holden, Kodama, Honjo, Lei, Varghese, Boyett, 2000</name>
    </entry>

  </entries>
<database>
```