#!/bin/bash
for i in $( ls filters ); do
	( cd filters/$i && rm *.o *.so  )
done
